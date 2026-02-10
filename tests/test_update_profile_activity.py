import datetime as dt
import sys
import os

# Add scripts directory to path to import the module
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from scripts.update_profile_activity import classify_repo, RepoResult

def test_classify_repo_archived():
    now = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
    metadata = {"full_name": "owner/repo", "archived": True, "pushed_at": "2023-01-01T12:00:00Z"}
    result = classify_repo(metadata, now, 10, 20)
    assert result.status == "archived"

def test_classify_repo_active():
    now = dt.datetime(2023, 1, 10, 12, 0, 0, tzinfo=dt.timezone.utc)
    # 5 days ago
    pushed_at = "2023-01-05T12:00:00Z"
    metadata = {"full_name": "owner/repo", "archived": False, "pushed_at": pushed_at}
    result = classify_repo(metadata, now, 10, 20)
    assert result.status == "active"

def test_classify_repo_partially():
    now = dt.datetime(2023, 1, 20, 12, 0, 0, tzinfo=dt.timezone.utc)
    # 15 days ago (active=10, partially=20)
    pushed_at = "2023-01-05T12:00:00Z"
    metadata = {"full_name": "owner/repo", "archived": False, "pushed_at": pushed_at}
    result = classify_repo(metadata, now, 10, 20)
    assert result.status == "partially"

def test_classify_repo_inactive():
    now = dt.datetime(2023, 2, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
    # 27 days ago (active=10, partially=20)
    pushed_at = "2023-01-05T12:00:00Z"
    metadata = {"full_name": "owner/repo", "archived": False, "pushed_at": pushed_at}
    result = classify_repo(metadata, now, 10, 20)
    assert result.status == "inactive"

def test_classify_repo_missing_z():
    now = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
    # Invalid format for strptime (missing Z), but fromisoformat accepts it.
    # Our code should default to UTC and treat it as active (since date matches now).
    pushed_at = "2023-01-01T12:00:00"
    metadata = {"full_name": "owner/repo", "archived": False, "pushed_at": pushed_at}
    result = classify_repo(metadata, now, 10, 20)
    assert result.status == "active"

def test_classify_repo_none_date():
    now = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
    metadata = {"full_name": "owner/repo", "archived": False, "pushed_at": None}
    result = classify_repo(metadata, now, 10, 20)
    assert result.status == "inactive"

def test_classify_repo_garbage_date():
    now = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
    metadata = {"full_name": "owner/repo", "archived": False, "pushed_at": "not-a-date"}
    result = classify_repo(metadata, now, 10, 20)
    assert result.status == "inactive"
