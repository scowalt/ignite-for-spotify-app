from __future__ import annotations

import errno
import fcntl
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from .clients.paseo import OriginMain


class StateError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True)
class Job:
    id: int
    project_id: int
    issue_id: str
    generation: int
    activation_activity: str | None
    status: str
    workspace: str | None
    agent_id: str | None
    branch: str | None
    pull_request: int | None
    failure_reason: str | None
    retry_of: int | None
    merge_observed: bool
    issue_resolved: bool
    agent_archived: bool
    workspace_removed: bool
    local_branch_removed: bool
    remote_branch_removed: bool
    launch_reference: str | None
    launch_commit_sha: str | None
    launch_marker: str | None
    auto_merge_requested: bool


_ACTIVE_STATUSES = ("queued", "working", "awaiting_merge")


class StateStore:
    def __init__(self, path: Path, busy_timeout_ms: int = 1_000) -> None:
        self.path = path
        self._lock: TextIO | None = None
        self.connection: sqlite3.Connection | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._acquire_lock()
            self.connection = sqlite3.connect(
                path, isolation_level=None, timeout=busy_timeout_ms / 1_000
            )
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA journal_mode=WAL")
            self.connection.execute("PRAGMA synchronous=FULL")
            self.connection.execute("PRAGMA foreign_keys=ON")
            self.connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
            self._migrate()
            self.integrity_check()
        except StateError:
            self.close()
            raise
        except (OSError, sqlite3.Error) as error:
            self.close()
            raise StateError("DATABASE", str(error)) from error

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        if self._lock is not None:
            fcntl.flock(self._lock.fileno(), fcntl.LOCK_UN)
            self._lock.close()
            self._lock = None

    def _acquire_lock(self) -> None:
        lock_path = self.path.with_name(f"{self.path.name}.lock")
        try:
            self._lock = lock_path.open("a+")
            fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if self._lock is not None:
                self._lock.close()
                self._lock = None
            if error.errno in {errno.EACCES, errno.EAGAIN}:
                raise StateError("LOCKED", str(lock_path)) from error
            raise

    @property
    def schema_version(self) -> int:
        return int(self._db.execute("PRAGMA user_version").fetchone()[0])

    @property
    def journal_mode(self) -> str:
        return str(self._db.execute("PRAGMA journal_mode").fetchone()[0]).lower()

    @property
    def _db(self) -> sqlite3.Connection:
        if self.connection is None:
            raise StateError("DATABASE", "store is closed")
        return self.connection

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection]:
        db = self._db
        try:
            db.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as error:
            raise StateError("DATABASE", str(error)) from error
        try:
            yield db
            db.execute("COMMIT")
        except sqlite3.Error as error:
            self._rollback()
            raise StateError("DATABASE", str(error)) from error
        except Exception:
            self._rollback()
            raise

    def _rollback(self) -> None:
        try:
            self._db.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    def _migrate(self) -> None:
        version = self.schema_version
        if version == 4:
            self._require_schema()
            return
        if version == 3:
            self._upgrade_v3()
            return
        if version == 2:
            self._upgrade_v2()
            self._upgrade_v3()
            return
        if version == 1:
            raise StateError("MIGRATION", "legacy transition ledger state is not supported")
        if version != 0:
            raise StateError("MIGRATION", "database is newer than this controller")
        self._db.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE settings (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            CREATE TABLE issues (
              project_id INTEGER NOT NULL,
              issue_id TEXT NOT NULL,
              status TEXT NOT NULL CHECK(status IN ('unresolved', 'resolved')),
              first_seen TEXT NOT NULL,
              activity TEXT NOT NULL,
              PRIMARY KEY(project_id, issue_id)
            );
            CREATE TABLE jobs (
              id INTEGER PRIMARY KEY,
              project_id INTEGER NOT NULL,
              issue_id TEXT NOT NULL,
              generation INTEGER NOT NULL CHECK(generation > 0),
              activation_activity TEXT,
              status TEXT NOT NULL CHECK(status IN ('queued', 'working', 'awaiting_merge', 'failed', 'complete')),
              workspace TEXT,
              agent_id TEXT,
              branch TEXT,
              pull_request INTEGER CHECK(pull_request IS NULL OR pull_request > 0),
              failure_reason TEXT,
              retry_of INTEGER REFERENCES jobs(id),
              merge_observed INTEGER NOT NULL DEFAULT 0 CHECK(merge_observed IN (0, 1)),
              issue_resolved INTEGER NOT NULL DEFAULT 0 CHECK(issue_resolved IN (0, 1)),
              agent_archived INTEGER NOT NULL DEFAULT 0 CHECK(agent_archived IN (0, 1)),
              workspace_removed INTEGER NOT NULL DEFAULT 0 CHECK(workspace_removed IN (0, 1)),
              local_branch_removed INTEGER NOT NULL DEFAULT 0 CHECK(local_branch_removed IN (0, 1)),
              remote_branch_removed INTEGER NOT NULL DEFAULT 0 CHECK(remote_branch_removed IN (0, 1)),
              launch_reference TEXT,
              launch_commit_sha TEXT,
              launch_marker TEXT,
              auto_merge_requested INTEGER NOT NULL DEFAULT 0 CHECK(auto_merge_requested IN (0, 1)),
              CHECK((status = 'failed' AND failure_reason IS NOT NULL) OR (status != 'failed' AND failure_reason IS NULL))
            );
            CREATE UNIQUE INDEX one_initial_job_per_activation
              ON jobs(project_id, issue_id, generation) WHERE retry_of IS NULL;
            CREATE UNIQUE INDEX one_active_job_per_activation
              ON jobs(project_id, issue_id, generation)
              WHERE status IN ('queued', 'working', 'awaiting_merge');
            CREATE UNIQUE INDEX one_retry_per_failed_job
              ON jobs(retry_of) WHERE retry_of IS NOT NULL;
            PRAGMA user_version=4;
            COMMIT;
            """
        )

    def _upgrade_v2(self) -> None:
        try:
            self._db.executescript(
                """
                BEGIN IMMEDIATE;
                ALTER TABLE jobs ADD COLUMN merge_observed INTEGER NOT NULL DEFAULT 0;
                ALTER TABLE jobs ADD COLUMN issue_resolved INTEGER NOT NULL DEFAULT 0;
                ALTER TABLE jobs ADD COLUMN agent_archived INTEGER NOT NULL DEFAULT 0;
                ALTER TABLE jobs ADD COLUMN workspace_removed INTEGER NOT NULL DEFAULT 0;
                ALTER TABLE jobs ADD COLUMN local_branch_removed INTEGER NOT NULL DEFAULT 0;
                ALTER TABLE jobs ADD COLUMN remote_branch_removed INTEGER NOT NULL DEFAULT 0;
                UPDATE jobs
                SET merge_observed=1,
                    issue_resolved=1,
                    agent_archived=1,
                    workspace_removed=1,
                    local_branch_removed=1,
                    remote_branch_removed=1
                WHERE status='complete';
                PRAGMA user_version=3;
                COMMIT;
                """
            )
        except sqlite3.Error as error:
            self._rollback()
            raise StateError("MIGRATION", str(error)) from error

    def _upgrade_v3(self) -> None:
        try:
            self._db.executescript(
                """
                BEGIN IMMEDIATE;
                ALTER TABLE jobs ADD COLUMN activation_activity TEXT;
                ALTER TABLE jobs ADD COLUMN launch_reference TEXT;
                ALTER TABLE jobs ADD COLUMN launch_commit_sha TEXT;
                ALTER TABLE jobs ADD COLUMN launch_marker TEXT;
                ALTER TABLE jobs ADD COLUMN auto_merge_requested INTEGER NOT NULL DEFAULT 0;
                PRAGMA user_version=4;
                COMMIT;
                """
            )
            self._require_schema()
        except sqlite3.Error as error:
            self._rollback()
            raise StateError("MIGRATION", str(error)) from error

    def _require_schema(self) -> None:
        required = {"settings", "issues", "jobs"}
        found = {
            str(row["name"])
            for row in self._db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        columns = {str(row["name"]) for row in self._db.execute("PRAGMA table_info(jobs)")}
        progress = {
            "merge_observed",
            "issue_resolved",
            "agent_archived",
            "workspace_removed",
            "local_branch_removed",
            "remote_branch_removed",
            "activation_activity",
            "launch_reference",
            "launch_commit_sha",
            "launch_marker",
            "auto_merge_requested",
        }
        if not required.issubset(found) or not progress.issubset(columns):
            raise StateError("MIGRATION", "database is missing the compact job schema")

    def set_baseline(self, cutoff: str) -> None:
        if not cutoff:
            raise StateError("INVALID_BASELINE")
        with self.transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES('baseline_cutoff', ?)", (cutoff,)
            )

    def baseline_cutoff(self) -> str | None:
        row = self._db.execute("SELECT value FROM settings WHERE key='baseline_cutoff'").fetchone()
        return None if row is None else str(row["value"])

    def queue_job(
        self,
        project_id: int,
        issue_id: str,
        generation: int,
        *,
        activation_activity: str | None = None,
        retry_of: int | None = None,
    ) -> Job:
        with self.transaction() as db:
            job_id = self._insert_job(
                db,
                project_id,
                issue_id,
                generation,
                activation_activity=activation_activity,
                retry_of=retry_of,
            )
            return self._job_from_row(self._job_row(db, job_id))

    def _insert_job(
        self,
        db: sqlite3.Connection,
        project_id: int,
        issue_id: str,
        generation: int,
        *,
        activation_activity: str | None,
        retry_of: int | None,
    ) -> int:
        if retry_of is None:
            initial = db.execute(
                """
                SELECT id FROM jobs
                WHERE project_id=? AND issue_id=? AND generation=? AND retry_of IS NULL
                """,
                (project_id, issue_id, generation),
            ).fetchone()
            if initial is not None:
                raise StateError("JOB_EXISTS")
        active = db.execute(
            """
            SELECT id FROM jobs
            WHERE project_id=? AND issue_id=? AND generation=?
              AND status IN ('queued', 'working', 'awaiting_merge')
            """,
            (project_id, issue_id, generation),
        ).fetchone()
        if active is not None:
            raise StateError("ACTIVE_JOB_EXISTS")
        if (
            retry_of is not None
            and db.execute("SELECT id FROM jobs WHERE retry_of=?", (retry_of,)).fetchone()
            is not None
        ):
            raise StateError("RETRY_EXISTS")
        try:
            cursor = db.execute(
                """
                INSERT INTO jobs(project_id, issue_id, generation, activation_activity, status, retry_of)
                VALUES(?, ?, ?, ?, 'queued', ?)
                """,
                (project_id, issue_id, generation, activation_activity, retry_of),
            )
        except sqlite3.IntegrityError as error:
            raise StateError("JOB_EXISTS") from error
        if cursor.lastrowid is None:
            raise StateError("DATABASE", "job insert returned no ID")
        return int(cursor.lastrowid)

    def job(self, job_id: int) -> Job:
        return self._job_from_row(self._job_row(self._db, job_id))

    def jobs(self) -> tuple[Job, ...]:
        return tuple(
            self._job_from_row(row) for row in self._db.execute("SELECT * FROM jobs ORDER BY id")
        )

    def _job_row(self, db: sqlite3.Connection, job_id: int) -> sqlite3.Row:
        row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise StateError("JOB_NOT_FOUND")
        return row

    @staticmethod
    def _job_from_row(row: sqlite3.Row) -> Job:
        return Job(
            id=int(row["id"]),
            project_id=int(row["project_id"]),
            issue_id=str(row["issue_id"]),
            generation=int(row["generation"]),
            activation_activity=(
                None if row["activation_activity"] is None else str(row["activation_activity"])
            ),
            status=str(row["status"]),
            workspace=None if row["workspace"] is None else str(row["workspace"]),
            agent_id=None if row["agent_id"] is None else str(row["agent_id"]),
            branch=None if row["branch"] is None else str(row["branch"]),
            pull_request=None if row["pull_request"] is None else int(row["pull_request"]),
            failure_reason=(None if row["failure_reason"] is None else str(row["failure_reason"])),
            retry_of=None if row["retry_of"] is None else int(row["retry_of"]),
            merge_observed=bool(row["merge_observed"]),
            issue_resolved=bool(row["issue_resolved"]),
            agent_archived=bool(row["agent_archived"]),
            workspace_removed=bool(row["workspace_removed"]),
            local_branch_removed=bool(row["local_branch_removed"]),
            remote_branch_removed=bool(row["remote_branch_removed"]),
            launch_reference=(
                None if row["launch_reference"] is None else str(row["launch_reference"])
            ),
            launch_commit_sha=(
                None if row["launch_commit_sha"] is None else str(row["launch_commit_sha"])
            ),
            launch_marker=None if row["launch_marker"] is None else str(row["launch_marker"]),
            auto_merge_requested=bool(row["auto_merge_requested"]),
        )

    def start_job(self, job_id: int) -> Job:
        return self._transition_job(job_id, "queued", "working")

    def await_merge(self, job_id: int) -> Job:
        return self._transition_job(job_id, "working", "awaiting_merge")

    def record_auto_merge_requested(self, job_id: int) -> Job:
        with self.transaction() as db:
            row = self._job_row(db, job_id)
            if row["status"] != "awaiting_merge" or row["pull_request"] is None:
                raise StateError("STATE_MISMATCH", "expected awaiting merge with a pull request")
            if not bool(row["auto_merge_requested"]):
                db.execute("UPDATE jobs SET auto_merge_requested=1 WHERE id=?", (job_id,))
            return self._job_from_row(self._job_row(db, job_id))

    def complete_job(self, job_id: int) -> Job:
        with self.transaction() as db:
            row = self._job_row(db, job_id)
            if row["status"] != "awaiting_merge":
                raise StateError("STATE_MISMATCH", "expected awaiting_merge")
            fields = (
                "merge_observed",
                "issue_resolved",
                "agent_archived",
                "workspace_removed",
                "local_branch_removed",
                "remote_branch_removed",
            )
            if not all(bool(row[field]) for field in fields):
                raise StateError("STATE_MISMATCH", "lifecycle cleanup is incomplete")
            db.execute("UPDATE jobs SET status='complete' WHERE id=?", (job_id,))
            return self._job_from_row(self._job_row(db, job_id))

    def record_merge_observed(self, job_id: int) -> Job:
        return self._record_lifecycle_checkpoint(job_id, "merge_observed", ())

    def record_issue_resolved(self, job_id: int, *, first_seen: str, activity: str) -> Job:
        if not first_seen or not activity:
            raise StateError("INVALID_ISSUE_OBSERVATION")
        with self.transaction() as db:
            row = self._job_row(db, job_id)
            if row["status"] != "awaiting_merge":
                raise StateError("STATE_MISMATCH", "expected awaiting_merge")
            if not bool(row["merge_observed"]):
                raise StateError("STATE_MISMATCH", "lifecycle checkpoint is out of order")
            prior = db.execute(
                "SELECT first_seen FROM issues WHERE project_id=? AND issue_id=?",
                (row["project_id"], row["issue_id"]),
            ).fetchone()
            if prior is None:
                db.execute(
                    """
                    INSERT INTO issues(project_id, issue_id, status, first_seen, activity)
                    VALUES(?, ?, 'resolved', ?, ?)
                    """,
                    (row["project_id"], row["issue_id"], first_seen, activity),
                )
            else:
                db.execute(
                    """
                    UPDATE issues
                    SET status='resolved', first_seen=MIN(first_seen, ?), activity=?
                    WHERE project_id=? AND issue_id=?
                    """,
                    (first_seen, activity, row["project_id"], row["issue_id"]),
                )
            if not bool(row["issue_resolved"]):
                db.execute("UPDATE jobs SET issue_resolved=1 WHERE id=?", (job_id,))
            return self._job_from_row(self._job_row(db, job_id))

    def record_agent_archived(self, job_id: int) -> Job:
        return self._record_lifecycle_checkpoint(job_id, "agent_archived", ("issue_resolved",))

    def record_workspace_removed(self, job_id: int) -> Job:
        return self._record_lifecycle_checkpoint(job_id, "workspace_removed", ("agent_archived",))

    def record_local_branch_removed(self, job_id: int) -> Job:
        return self._record_lifecycle_checkpoint(
            job_id, "local_branch_removed", ("workspace_removed",)
        )

    def record_remote_branch_removed(self, job_id: int) -> Job:
        return self._record_lifecycle_checkpoint(
            job_id, "remote_branch_removed", ("local_branch_removed",)
        )

    def _record_lifecycle_checkpoint(
        self, job_id: int, field: str, prerequisites: tuple[str, ...]
    ) -> Job:
        with self.transaction() as db:
            row = self._job_row(db, job_id)
            if row["status"] != "awaiting_merge":
                raise StateError("STATE_MISMATCH", "expected awaiting_merge")
            if not all(bool(row[prerequisite]) for prerequisite in prerequisites):
                raise StateError("STATE_MISMATCH", "lifecycle checkpoint is out of order")
            if not bool(row[field]):
                db.execute(f"UPDATE jobs SET {field}=1 WHERE id=?", (job_id,))
            return self._job_from_row(self._job_row(db, job_id))

    def _transition_job(self, job_id: int, expected: str, target: str) -> Job:
        with self.transaction() as db:
            row = self._job_row(db, job_id)
            if row["status"] != expected:
                raise StateError("STATE_MISMATCH", f"expected {expected}")
            db.execute("UPDATE jobs SET status=? WHERE id=?", (target, job_id))
            return self._job_from_row(self._job_row(db, job_id))

    def record_launch_intent(
        self,
        job_id: int,
        *,
        workspace: str,
        agent_id: str,
        branch: str,
        base: OriginMain,
        marker: str,
    ) -> Job:
        if not all((workspace, agent_id, branch, base.reference, base.commit_sha, marker)):
            raise StateError("INVALID_LAUNCH_INTENT")
        with self.transaction() as db:
            row = self._job_row(db, job_id)
            if row["status"] != "working":
                raise StateError("STATE_MISMATCH", "expected working")
            intent = (workspace, agent_id, branch, base.reference, base.commit_sha, marker)
            recorded = (
                row["workspace"],
                row["agent_id"],
                row["branch"],
                row["launch_reference"],
                row["launch_commit_sha"],
                row["launch_marker"],
            )
            if any(value is not None for value in recorded):
                if recorded != intent:
                    raise StateError("LAUNCH_INTENT_MISMATCH")
                return self._job_from_row(row)
            db.execute(
                """
                UPDATE jobs
                SET workspace=?, agent_id=?, branch=?, launch_reference=?, launch_commit_sha=?,
                    launch_marker=?
                WHERE id=?
                """,
                (*intent, job_id),
            )
            return self._job_from_row(self._job_row(db, job_id))

    def record_resources(
        self,
        job_id: int,
        *,
        workspace: str | None = None,
        agent_id: str | None = None,
        branch: str | None = None,
        pull_request: int | None = None,
    ) -> Job:
        values = (workspace, agent_id, branch, pull_request)
        if all(value is None for value in values):
            raise StateError("MISSING_RESOURCE")
        if any(not value for value in values[:3] if value is not None):
            raise StateError("INVALID_RESOURCE")
        if pull_request is not None and pull_request < 1:
            raise StateError("INVALID_RESOURCE")
        with self.transaction() as db:
            self._job_row(db, job_id)
            db.execute(
                """
                UPDATE jobs
                SET workspace=COALESCE(?, workspace),
                    agent_id=COALESCE(?, agent_id),
                    branch=COALESCE(?, branch),
                    pull_request=COALESCE(?, pull_request)
                WHERE id=?
                """,
                (workspace, agent_id, branch, pull_request, job_id),
            )
            return self._job_from_row(self._job_row(db, job_id))

    def fail_job(self, job_id: int, reason: str) -> Job:
        if not reason:
            raise StateError("INVALID_FAILURE_REASON")
        with self.transaction() as db:
            row = self._job_row(db, job_id)
            if str(row["status"]) not in _ACTIVE_STATUSES:
                raise StateError("STATE_MISMATCH", "only active jobs can fail")
            db.execute(
                "UPDATE jobs SET status='failed', failure_reason=? WHERE id=?", (reason, job_id)
            )
            return self._job_from_row(self._job_row(db, job_id))

    def retry_job(self, job_id: int) -> Job:
        with self.transaction() as db:
            failed = self._job_row(db, job_id)
            if failed["status"] != "failed":
                raise StateError("RETRY_REQUIRES_FAILED_JOB")
            if self._has_persisted_resources(failed):
                raise StateError(
                    "RETRY_REQUIRES_RESOURCE_RESOLUTION",
                    "operator must resolve, clean, or adopt the existing resources first",
                )
            retry_id = self._insert_job(
                db,
                int(failed["project_id"]),
                str(failed["issue_id"]),
                int(failed["generation"]),
                activation_activity=(
                    None
                    if failed["activation_activity"] is None
                    else str(failed["activation_activity"])
                ),
                retry_of=job_id,
            )
            return self._job_from_row(self._job_row(db, retry_id))

    @staticmethod
    def _has_persisted_resources(job: sqlite3.Row) -> bool:
        return any(
            job[field] is not None
            for field in (
                "workspace",
                "agent_id",
                "branch",
                "pull_request",
                "launch_reference",
                "launch_commit_sha",
                "launch_marker",
            )
        ) or any(
            bool(job[field])
            for field in (
                "merge_observed",
                "issue_resolved",
                "agent_archived",
                "workspace_removed",
                "local_branch_removed",
                "remote_branch_removed",
            )
        )

    def ingest_listing_observations(
        self, cutoff: str, observations: tuple[tuple[int, str, str, str, str], ...]
    ) -> None:
        with self.transaction() as db:
            self._require_baseline(db, cutoff)
            for project_id, issue_id, status, first_seen, activity in observations:
                self._ingest_observation(
                    db, project_id, issue_id, status, first_seen, activity, cutoff
                )

    def observe_detail(
        self,
        cutoff: str,
        project_id: int,
        issue_id: str,
        status: str,
        first_seen: str,
        activity: str,
    ) -> None:
        with self.transaction() as db:
            self._require_baseline(db, cutoff)
            self._ingest_observation(db, project_id, issue_id, status, first_seen, activity, cutoff)

    @staticmethod
    def _require_baseline(db: sqlite3.Connection, cutoff: str) -> None:
        row = db.execute("SELECT value FROM settings WHERE key='baseline_cutoff'").fetchone()
        if row is None:
            raise StateError("BASELINE_CUTOFF_REQUIRED")
        if str(row["value"]) != cutoff:
            raise StateError("BASELINE_CUTOFF_MISMATCH")

    def _ingest_observation(
        self,
        db: sqlite3.Connection,
        project_id: int,
        issue_id: str,
        status: str,
        first_seen: str,
        activity: str,
        cutoff: str,
    ) -> None:
        if status not in {"unresolved", "resolved"}:
            raise StateError("INVALID_ISSUE_STATUS")
        if not issue_id or not first_seen or not activity:
            raise StateError("INVALID_ISSUE_OBSERVATION")
        prior = db.execute(
            "SELECT status, activity FROM issues WHERE project_id=? AND issue_id=?",
            (project_id, issue_id),
        ).fetchone()
        if prior is not None and (
            activity < str(prior["activity"])
            or (activity == str(prior["activity"]) and status == str(prior["status"]))
        ):
            return
        if prior is None:
            db.execute(
                """
                INSERT INTO issues(project_id, issue_id, status, first_seen, activity)
                VALUES(?, ?, ?, ?, ?)
                """,
                (project_id, issue_id, status, first_seen, activity),
            )
            if status == "unresolved" and first_seen > cutoff:
                self._insert_job(
                    db,
                    project_id,
                    issue_id,
                    1,
                    activation_activity=activity,
                    retry_of=None,
                )
            return

        db.execute(
            """
            UPDATE issues
            SET status=?, first_seen=MIN(first_seen, ?), activity=?
            WHERE project_id=? AND issue_id=?
            """,
            (status, first_seen, activity, project_id, issue_id),
        )
        if prior["status"] == "resolved" and status == "unresolved":
            row = db.execute(
                """
                SELECT COALESCE(MAX(generation), 0) AS generation
                FROM jobs WHERE project_id=? AND issue_id=?
                """,
                (project_id, issue_id),
            ).fetchone()
            self._insert_job(
                db,
                project_id,
                issue_id,
                int(row["generation"]) + 1,
                activation_activity=activity,
                retry_of=None,
            )

    def activation_is_current(self, job_id: int) -> bool:
        job = self.job(job_id)
        generation = self._db.execute(
            "SELECT COALESCE(MAX(generation), 0) FROM jobs WHERE project_id=? AND issue_id=?",
            (job.project_id, job.issue_id),
        ).fetchone()
        return generation is not None and int(generation[0]) == job.generation

    def issue(self, project_id: int, issue_id: str) -> sqlite3.Row | None:
        return self._db.execute(
            "SELECT * FROM issues WHERE project_id=? AND issue_id=?", (project_id, issue_id)
        ).fetchone()

    def issues(self) -> tuple[sqlite3.Row, ...]:
        return tuple(self._db.execute("SELECT * FROM issues ORDER BY project_id, issue_id"))

    def integrity_check(self) -> None:
        try:
            result = self._db.execute("PRAGMA integrity_check").fetchone()
            if result is None or result[0] != "ok":
                raise StateError("INTEGRITY")
        except sqlite3.Error as error:
            raise StateError("DATABASE", str(error)) from error

    def backup(self, destination: Path) -> Path:
        target: sqlite3.Connection | None = None
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            target = sqlite3.connect(destination)
            self._db.backup(target)
            return destination
        except (OSError, sqlite3.Error) as error:
            raise StateError("BACKUP", str(error)) from error
        finally:
            if target is not None:
                target.close()
