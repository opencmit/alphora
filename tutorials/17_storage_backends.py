"""
Tutorial 17: Storage backends (memory/json/sqlite) + transaction/TTL/serializer.

Run:
  python tutorials/17_storage_backends.py
"""

import tempfile
from pathlib import Path
from datetime import datetime

from alphora.memory import MemoryManager
from alphora.storage import JSONStorage, SQLiteStorage, StorageConfig
from alphora.storage.serializers import JSONSerializer


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        json_path = str(base / "memory.json")
        sqlite_path = str(base / "memory.db")

        # JSON storage with compression and auto-save
        json_cfg = StorageConfig(path=json_path, compression=True, auto_save=True, save_interval=1)
        storage_json = JSONStorage(config=json_cfg)
        with storage_json.transaction():
            storage_json.set("user:1:name", "Alice")
            storage_json.set("user:1:created", datetime.utcnow())
            storage_json.lpush("user:1:history", {"role": "user", "content": "hello"})

        storage_json.expire("user:1:name", 5)
        print("TTL:", storage_json.ttl("user:1:name"))

        # JSON serializer demo
        serializer = JSONSerializer(indent=2)
        encoded = serializer.serialize_to_string({"time": datetime.utcnow()})
        decoded = serializer.deserialize_from_string(encoded)
        print("Serializer decoded:", decoded)

        # SQLite storage with transaction
        storage_sqlite = SQLiteStorage(sqlite_path)
        with storage_sqlite.transaction():
            storage_sqlite.set("k1", "v1")
            storage_sqlite.set("k2", "v2")

        # MemoryManager + storage types
        mem_json = MemoryManager(storage_type="json", storage_path=json_path)
        mem_json.add_user("Hello from JSON storage.")
        mem_json.add_assistant("JSON storage is persisted.")

        mem_sqlite = MemoryManager(storage_type="sqlite", storage_path=sqlite_path)
        mem_sqlite.add_user("Hello from SQLite storage.")
        mem_sqlite.add_assistant("SQLite storage is persisted.")

        print("JSON message_count:", mem_json.build_history().message_count)
        print("SQLite message_count:", mem_sqlite.build_history().message_count)


if __name__ == "__main__":
    main()
