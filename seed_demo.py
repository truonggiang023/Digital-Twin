"""Explicit, idempotent demo creation; never removes existing records."""
import argparse
from pathlib import Path
from project_store import ProjectStore
from lifecycle import api
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--database',type=Path,default=Path('data/workspace.sqlite3'))
    args=parser.parse_args();store=ProjectStore(args.database)
    try:print(api(store,'demo',{}))
    finally:store.close()
