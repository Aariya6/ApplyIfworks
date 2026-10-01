from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root for every entry point (cli, web server, tests)
# that imports the app package. Values already set in the real environment win.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
