import sqlite3
import json
from datetime import datetime, timezone
from db.schema import DB_FILE


def _utc_now() -> str:
    """Timezone-aware UTC timestamp formatted to match SQLite's CURRENT_TIMESTAMP."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn



def upsert_user(user_id: str, email: str, name: str = None, picture: str = None):
    """Create user if missing, update last_login otherwise."""
    conn = _conn()
    cur = conn.cursor()
    now = _utc_now()
    cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE users SET last_login = ?, name = COALESCE(?, name), picture = COALESCE(?, picture) WHERE user_id = ?",
            (now, name, picture, user_id),
        )
    else:
        cur.execute(
            "INSERT INTO users (user_id, email, name, picture, created_at, last_login) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, email, name, picture, now, now),
        )
    conn.commit()
    conn.close()


def get_user(user_id: str):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["skills"] = _split_csv(d.get("skills"))
    d["interests"] = _split_csv(d.get("interests"))
    return d


def _split_csv(s: str | None) -> list[str]:
    if not s:
        return []
    return [t.strip() for t in s.split(",") if t and t.strip()]


def _join_csv(items) -> str:
    if not items:
        return ""
    if isinstance(items, str):
        items = [t for t in items.split(",")]
    cleaned = []
    seen = set()
    for it in items:
        v = (it or "").strip()
        key = v.lower()
        if v and key not in seen:
            cleaned.append(v[:60])
            seen.add(key)
    return ", ".join(cleaned[:20])


def update_user_profile(user_id: str, *, display_name: str | None = None,
                        age: int | None = None, skills=None, interests=None,
                        learning_style: str | None = None) -> dict | None:
    """Persist profile personalisation fields. Returns the refreshed user dict."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cur.fetchone():
        conn.close()
        return None

    sets, params = [], []
    if display_name is not None:
        sets.append("display_name = ?")
        params.append((display_name or "").strip()[:80] or None)
    if age is not None:
        try:
            a = int(age)
            if a < 0 or a > 120:
                a = None
        except (TypeError, ValueError):
            a = None
        sets.append("age = ?")
        params.append(a)
    if skills is not None:
        sets.append("skills = ?")
        params.append(_join_csv(skills))
    if interests is not None:
        sets.append("interests = ?")
        params.append(_join_csv(interests))
    if learning_style is not None:
        sets.append("learning_style = ?")
        params.append((learning_style or "").strip()[:40] or None)
    sets.append("profile_updated_at = ?")
    params.append(_utc_now())
    params.append(user_id)

    cur.execute(f"UPDATE users SET {', '.join(sets)} WHERE user_id = ?", params)
    conn.commit()
    conn.close()
    return get_user(user_id)



def add_curriculum(user_id: str, goal: str, mode: str, title: str,
                   curriculum_json: dict, youtube_urls: list,
                   opportunities: list, web_trends: list,
                   timeframe_amount: int = 1, timeframe_unit: str = "day") -> int:
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO curricula
           (user_id, goal, mode, title, curriculum_json, youtube_urls_json, opportunities_json, web_trends_json,
            timeframe_amount, timeframe_unit)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id, goal, mode, title,
            json.dumps(curriculum_json or {}),
            json.dumps(youtube_urls or []),
            json.dumps(opportunities or []),
            json.dumps(web_trends or []),
            int(timeframe_amount or 1),
            (timeframe_unit or "day").lower(),
        ),
    )
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return cid


def get_curriculum(curriculum_id: int):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM curricula WHERE id = ?", (curriculum_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["curriculum_json"] = json.loads(d.get("curriculum_json") or "{}")
    d["youtube_urls"] = json.loads(d.get("youtube_urls_json") or "[]")
    d["opportunities"] = json.loads(d.get("opportunities_json") or "[]")
    d["web_trends"] = json.loads(d.get("web_trends_json") or "[]")
    return d


def get_user_curricula(user_id: str):
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, goal, mode, title, created_at, timeframe_amount, timeframe_unit
           FROM curricula WHERE user_id = ? ORDER BY created_at DESC""",
        (user_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def delete_curriculum(curriculum_id: int, user_id: str) -> bool:
    """Cascade-delete a curriculum and all related sessions, quizzes, doubts (user-scoped)."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM curricula WHERE id = ? AND user_id = ?", (curriculum_id, user_id))
    deleted = cur.rowcount > 0
    cur.execute("DELETE FROM study_sessions WHERE curriculum_id = ? AND user_id = ?", (curriculum_id, user_id))
    cur.execute("DELETE FROM quizzes WHERE curriculum_id = ? AND user_id = ?", (curriculum_id, user_id))
    cur.execute("DELETE FROM doubts WHERE curriculum_id = ? AND user_id = ?", (curriculum_id, user_id))
    cur.execute("DELETE FROM chats WHERE curriculum_id = ? AND user_id = ?", (curriculum_id, user_id))
    conn.commit()
    conn.close()
    return deleted



def add_session(user_id: str, curriculum_id: int, goal: str, module_name: str,
                module_description: str, module_day: int, duration_hours: float,
                scheduled_time: str, event_link: str = None, event_id: str = None,
                youtube_url: str = None) -> int:
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO study_sessions
           (user_id, curriculum_id, goal, module_name, module_description, module_day,
            duration_hours, scheduled_time, event_link, event_id, youtube_url)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, curriculum_id, goal, module_name, module_description, module_day,
         duration_hours, scheduled_time, event_link, event_id, youtube_url),
    )
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    return sid


def get_user_sessions(user_id: str, curriculum_id: int = None):
    conn = _conn()
    cur = conn.cursor()
    if curriculum_id is not None:
        cur.execute(
            "SELECT * FROM study_sessions WHERE user_id = ? AND curriculum_id = ? ORDER BY scheduled_time ASC",
            (user_id, curriculum_id),
        )
    else:
        cur.execute(
            "SELECT * FROM study_sessions WHERE user_id = ? ORDER BY scheduled_time ASC",
            (user_id,),
        )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_session(session_id: int, user_id: str):
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM study_sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def mark_session_complete(session_id: int, user_id: str) -> bool:
    """Mark complete and clear the linked calendar event id (caller is responsible
    for deleting the event from Google Calendar before calling this)."""
    conn = _conn()
    cur = conn.cursor()
    now = _utc_now()
    cur.execute(
        "UPDATE study_sessions SET status = 'completed', event_id = NULL, event_link = NULL, completed_at = ? WHERE id = ? AND user_id = ?",
        (now, session_id, user_id),
    )
    ok = cur.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def get_first_incomplete_module_day(user_id: str, curriculum_id: int) -> int | None:
    """Return the lowest module_day in this curriculum that is NOT yet completed.
    Used to enforce sequential mark-as-done — Day N can only be checked off after
    Days 1..N-1 are all done.
    """
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT MIN(module_day) AS d FROM study_sessions
           WHERE user_id = ? AND curriculum_id = ? AND status != 'completed'""",
        (user_id, curriculum_id),
    )
    row = cur.fetchone()
    conn.close()
    if not row or row["d"] is None:
        return None
    return int(row["d"])


def get_pending_sessions_for_curriculum(user_id: str, curriculum_id: int):
    """Pending = not yet completed. Used by the rescheduler to find the
    sessions it needs to push forward."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, module_day, scheduled_time, event_id, event_link, module_name,
                  module_description, goal, duration_hours, youtube_url
           FROM study_sessions
           WHERE user_id = ? AND curriculum_id = ? AND status != 'completed'
           ORDER BY module_day ASC, scheduled_time ASC""",
        (user_id, curriculum_id),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_user_curricula_with_timeframe(user_id: str):
    """Return curricula rows with timeframe metadata so the rescheduler can
    iterate one curriculum at a time."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, goal, title, timeframe_amount, timeframe_unit
           FROM curricula WHERE user_id = ?""",
        (user_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_learning_streak(user_id: str) -> dict:
    """Compute consecutive-day completion streak (current + best) and weekly velocity."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT DATE(completed_at) AS day FROM study_sessions WHERE user_id = ? AND completed_at IS NOT NULL ORDER BY day DESC",
        (user_id,),
    )
    days = [r["day"] for r in cur.fetchall() if r["day"]]
    cur.execute(
        "SELECT COUNT(*) AS c FROM study_sessions WHERE user_id = ? AND completed_at IS NOT NULL AND completed_at >= DATETIME('now', '-7 days')",
        (user_id,),
    )
    weekly = cur.fetchone()["c"] or 0
    conn.close()

    if not days:
        return {"current_streak": 0, "best_streak": 0, "weekly_completed": 0, "last_active": None}

    from datetime import datetime as _dt, timedelta as _td
    parsed = []
    for d in days:
        try:
            parsed.append(_dt.strptime(d, "%Y-%m-%d").date())
        except Exception:
            pass
    parsed = sorted(set(parsed), reverse=True)
    if not parsed:
        return {"current_streak": 0, "best_streak": 0, "weekly_completed": weekly, "last_active": None}

    today = _dt.utcnow().date()
    current = 0
    expected = today
    for d in parsed:
        if d == expected:
            current += 1
            expected = expected - _td(days=1)
        elif d == expected + _td(days=1):
            current = 1
            expected = d - _td(days=1)
        else:
            break

    best = 1
    run = 1
    for i in range(1, len(parsed)):
        if (parsed[i - 1] - parsed[i]).days == 1:
            run += 1
            best = max(best, run)
        else:
            run = 1

    return {
        "current_streak": current,
        "best_streak": max(best, current),
        "weekly_completed": weekly,
        "last_active": parsed[0].isoformat() if parsed else None,
    }


def get_all_event_ids(user_id: str = None) -> list[str]:
    conn = _conn()
    cur = conn.cursor()
    if user_id:
        cur.execute("SELECT event_id FROM study_sessions WHERE event_id IS NOT NULL AND user_id = ?", (user_id,))
    else:
        cur.execute("SELECT event_id FROM study_sessions WHERE event_id IS NOT NULL")
    ids = [r[0] for r in cur.fetchall()]
    conn.close()
    return ids


def get_missed_sessions(current_time: str, user_id: str = None):
    """Returns full session rows that are past-due and still pending/rescheduled."""
    conn = _conn()
    cur = conn.cursor()
    cols = "id, goal, module_name, module_description, module_day, duration_hours, scheduled_time, event_id, event_link, curriculum_id, youtube_url"
    if user_id:
        cur.execute(
            f"SELECT {cols} FROM study_sessions WHERE scheduled_time < ? AND status IN ('pending', 'rescheduled') AND user_id = ?",
            (current_time, user_id),
        )
    else:
        cur.execute(
            f"SELECT {cols} FROM study_sessions WHERE scheduled_time < ? AND status IN ('pending', 'rescheduled')",
            (current_time,),
        )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def update_session_status(session_id: int, new_time: str, new_link: str = None,
                          new_event_id: str = None, status: str = 'rescheduled'):
    """Update a session after a reschedule. event_id may be replaced with a new one."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE study_sessions SET scheduled_time = ?, event_link = ?, event_id = ?, status = ? WHERE id = ?",
        (new_time, new_link, new_event_id, status, session_id),
    )
    conn.commit()
    conn.close()


def reset_user_data(user_id: str):
    """Clears all of a user's data."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM study_sessions WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM quizzes WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM doubts WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM chats WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM curricula WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()



def add_quiz(user_id: str, curriculum_id: int, module_day: int, module_topic: str, questions: list) -> int:
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO quizzes (user_id, curriculum_id, module_day, module_topic, questions_json, total)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, curriculum_id, module_day, module_topic, json.dumps(questions), len(questions)),
    )
    qid = cur.lastrowid
    conn.commit()
    conn.close()
    return qid


def get_quiz(quiz_id: int, user_id: str):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM quizzes WHERE id = ? AND user_id = ?", (quiz_id, user_id))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["questions"] = json.loads(d.get("questions_json") or "[]")
    return d


def get_quiz_for_module(user_id: str, curriculum_id: int, module_day: int):
    """Return the most recent quiz for this module, if any."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM quizzes WHERE user_id = ? AND curriculum_id = ? AND module_day = ? ORDER BY created_at DESC LIMIT 1",
        (user_id, curriculum_id, module_day),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["questions"] = json.loads(d.get("questions_json") or "[]")
    return d


def submit_quiz_score(quiz_id: int, user_id: str, score: int) -> bool:
    conn = _conn()
    cur = conn.cursor()
    now = _utc_now()
    cur.execute(
        "UPDATE quizzes SET score = ?, attempted_at = ? WHERE id = ? AND user_id = ?",
        (score, now, quiz_id, user_id),
    )
    ok = cur.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def get_quiz_progress(user_id: str, curriculum_id: int = None) -> dict:
    """Aggregate quiz stats for a user, optionally scoped to one curriculum."""
    conn = _conn()
    cur = conn.cursor()
    if curriculum_id is not None:
        cur.execute(
            "SELECT score, total, attempted_at FROM quizzes WHERE user_id = ? AND curriculum_id = ?",
            (user_id, curriculum_id),
        )
    else:
        cur.execute(
            "SELECT score, total, attempted_at FROM quizzes WHERE user_id = ?",
            (user_id,),
        )
    rows = cur.fetchall()
    conn.close()
    total_quizzes = len(rows)
    attempted = [r for r in rows if r["score"] is not None]
    sum_score = sum(r["score"] or 0 for r in attempted)
    sum_total = sum(r["total"] or 0 for r in attempted)
    accuracy = round((sum_score / sum_total) * 100) if sum_total else 0
    return {
        "quizzes_total": total_quizzes,
        "quizzes_attempted": len(attempted),
        "points_earned": sum_score,
        "points_possible": sum_total,
        "accuracy_pct": accuracy,
    }



def add_doubt(user_id: str, question: str, answer: str,
              curriculum_id: int = None, module_day: int = None,
              chat_id: int = None) -> int:
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO doubts (user_id, curriculum_id, module_day, question, answer, chat_id) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, curriculum_id, module_day, question, answer, chat_id),
    )
    did = cur.lastrowid
    conn.commit()
    conn.close()
    return did


def get_user_doubts(user_id: str, curriculum_id: int = None, limit: int = 50):
    conn = _conn()
    cur = conn.cursor()
    if curriculum_id is not None:
        cur.execute(
            "SELECT * FROM doubts WHERE user_id = ? AND curriculum_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, curriculum_id, limit),
        )
    else:
        cur.execute(
            "SELECT * FROM doubts WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows



def create_chat(user_id: str, curriculum_id: int = None,
                module_day: int = None, title: str = "New chat") -> int:
    """Create a new chat thread for the user."""
    conn = _conn()
    cur = conn.cursor()
    now = _utc_now()
    cur.execute(
        "INSERT INTO chats (user_id, curriculum_id, module_day, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, curriculum_id, module_day, title, now, now),
    )
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return cid


def get_user_chats(user_id: str, curriculum_id: int = None, limit: int = 50):
    """List chat threads for a user, newest first."""
    conn = _conn()
    cur = conn.cursor()
    if curriculum_id is not None:
        cur.execute(
            """SELECT c.id, c.user_id, c.curriculum_id, c.module_day, c.title, c.created_at, c.updated_at,
                      (SELECT COUNT(*) FROM doubts d WHERE d.chat_id = c.id) AS message_count
               FROM chats c
               WHERE c.user_id = ? AND c.curriculum_id = ?
               ORDER BY c.updated_at DESC LIMIT ?""",
            (user_id, curriculum_id, limit),
        )
    else:
        cur.execute(
            """SELECT c.id, c.user_id, c.curriculum_id, c.module_day, c.title, c.created_at, c.updated_at,
                      (SELECT COUNT(*) FROM doubts d WHERE d.chat_id = c.id) AS message_count
               FROM chats c
               WHERE c.user_id = ?
               ORDER BY c.updated_at DESC LIMIT ?""",
            (user_id, limit),
        )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_chat(chat_id: int, user_id: str):
    """Return chat metadata + ordered messages (oldest first)."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM chats WHERE id = ? AND user_id = ?",
        (chat_id, user_id),
    )
    chat_row = cur.fetchone()
    if not chat_row:
        conn.close()
        return None
    chat = dict(chat_row)
    cur.execute(
        "SELECT id, question, answer, created_at FROM doubts WHERE chat_id = ? AND user_id = ? ORDER BY id ASC",
        (chat_id, user_id),
    )
    chat["messages"] = [dict(r) for r in cur.fetchall()]
    conn.close()
    return chat


def get_chat_history(chat_id: int, user_id: str, limit: int = 8) -> list[dict]:
    """Return the last N (question, answer) turns for a chat, oldest first.
    Used to feed conversational context into the AI tutor."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT question, answer FROM doubts WHERE chat_id = ? AND user_id = ? ORDER BY id DESC LIMIT ?",
        (chat_id, user_id, limit),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    rows.reverse()
    return rows


def touch_chat(chat_id: int, user_id: str, title: str = None):
    """Bump updated_at; optionally set/replace the title (useful on first message)."""
    conn = _conn()
    cur = conn.cursor()
    now = _utc_now()
    if title is not None:
        cur.execute(
            "UPDATE chats SET updated_at = ?, title = ? WHERE id = ? AND user_id = ?",
            (now, title, chat_id, user_id),
        )
    else:
        cur.execute(
            "UPDATE chats SET updated_at = ? WHERE id = ? AND user_id = ?",
            (now, chat_id, user_id),
        )
    conn.commit()
    conn.close()


def rename_chat(chat_id: int, user_id: str, title: str) -> bool:
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE chats SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (title, _utc_now(), chat_id, user_id),
    )
    ok = cur.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def delete_chat(chat_id: int, user_id: str) -> bool:
    conn = _conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM doubts WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    cur.execute("DELETE FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id))
    ok = cur.rowcount > 0
    conn.commit()
    conn.close()
    return ok
