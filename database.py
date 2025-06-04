import sqlite3
from config import DATABASE_FILE, ADMIN_IDS, ADMIN_USERNAMES

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_FILE)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        # Таблица пользователей
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                status TEXT NOT NULL
            )
        ''')
        
        # Таблица предложений
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                desired_status TEXT NOT NULL,
                proof TEXT NOT NULL,
                reason TEXT NOT NULL,
                suggested_by TEXT NOT NULL,
                suggested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        ''')
        
        # Таблица заблокированных пользователей
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS blocked_users (
                user_id TEXT PRIMARY KEY
            )
        ''')
        
        # Таблица пользователей бота
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_users (
                user_id TEXT PRIMARY KEY
            )
        ''')
        
        self.conn.commit()

    def add_bot_user(self, user_id: str):
        try:
            self.cursor.execute('''
                INSERT OR IGNORE INTO bot_users (user_id) VALUES (?)
            ''', (user_id,))
            self.conn.commit()
        except Exception as e:
            print(f"Ошибка добавления пользователя бота: {e}")

    def get_all_bot_users(self) -> list:
        self.cursor.execute('SELECT user_id FROM bot_users')
        return [row[0] for row in self.cursor.fetchall()]
    
    def get_total_bot_users(self) -> int:
        self.cursor.execute('SELECT COUNT(*) FROM bot_users')
        return self.cursor.fetchone()[0]
    
    def get_total_listed_users(self) -> int:
        self.cursor.execute('SELECT COUNT(*) FROM users')
        return self.cursor.fetchone()[0]
    
    def get_status_counts(self) -> dict:
        self.cursor.execute('''
            SELECT status, COUNT(*) as count 
            FROM users 
            GROUP BY status
        ''')
        return {row[0]: row[1] for row in self.cursor.fetchall()}

    def block_user(self, username: str) -> bool:
        try:
            self.cursor.execute('''
                INSERT OR IGNORE INTO blocked_users (user_id) VALUES (?)
            ''', (username,))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            print(f"Ошибка блокировки пользователя: {e}")
            return False

    def unblock_user(self, username: str) -> bool:
        try:
            self.cursor.execute('''
                DELETE FROM blocked_users WHERE user_id = ?
            ''', (username,))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            print(f"Ошибка разблокировки пользователя: {e}")
            return False

    def is_user_blocked(self, user_id: str) -> bool:
        self.cursor.execute('''
            SELECT 1 FROM blocked_users WHERE user_id = ?
        ''', (user_id,))
        return self.cursor.fetchone() is not None

    def add_suggestion(self, username: str, desired_status: str, proof: str, reason: str, suggested_by: str):
        self.cursor.execute('''
            INSERT INTO suggestions (username, desired_status, proof, reason, suggested_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (username.lower(), desired_status.lower(), proof, reason, suggested_by.lower()))
        self.conn.commit()

    def get_pending_suggestions(self):
        self.cursor.execute('SELECT * FROM suggestions WHERE status = "pending" ORDER BY suggested_at DESC')
        return self.cursor.fetchall()

    def update_suggestion_status(self, suggestion_id: int, status: str):
        self.cursor.execute('''
            UPDATE suggestions SET status = ? WHERE id = ?
        ''', (status.lower(), suggestion_id))
        self.conn.commit()

    def add_user(self, username: str, status: str):
        self.cursor.execute('INSERT OR REPLACE INTO users VALUES (?, ?)', (username.lower(), status))
        self.conn.commit()

    def remove_user(self, username: str):
        self.cursor.execute('DELETE FROM users WHERE username = ?', (username.lower(),))
        self.conn.commit()

    def get_user_status(self, username: str) -> str:
        self.cursor.execute('SELECT status FROM users WHERE username = ?', (username.lower(),))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def get_all_users(self) -> list:
        self.cursor.execute('''
            SELECT username, status FROM users 
            ORDER BY CASE status
                WHEN "admin" THEN 1
                WHEN "verify" THEN 2
                WHEN "garant" THEN 3
                WHEN "media" THEN 4
                WHEN "fame" THEN 5
                WHEN "scam" THEN 6
                WHEN "beach" THEN 7
                WHEN "new" THEN 8
                ELSE 9
            END
        ''')
        db_users = self.cursor.fetchall()
        
        admin_users = []
        for admin_id in ADMIN_IDS:
            username = ADMIN_USERNAMES.get(str(admin_id), str(admin_id))
            admin_users.append((username, 'admin'))
        
        all_users = admin_users + [
            user for user in db_users 
            if user[0] not in {str(admin_id) for admin_id in ADMIN_IDS}
        ]
        
        return all_users

    def close(self):
        self.conn.close()