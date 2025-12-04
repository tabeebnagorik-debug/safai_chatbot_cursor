# PostgreSQL Chat History Storage Setup

## ✅ Configuration Complete

Your chat history is now stored persistently in PostgreSQL!

## Database Configuration

**Current Settings:**
- **Host:** `localhost` (can be changed via `DB_HOST` env var)
- **Port:** `5432` (can be changed via `DB_PORT` env var)
- **Database:** `safai_chat_db` (can be changed via `DB_NAME` env var)
- **User:** `postgres` (can be changed via `DB_USER` env var)
- **Password:** Empty (set via `DB_PASSWORD` env var if needed)

## Environment Variables

You can customize the database connection by setting these in your `.env` file:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=safai_chat_db
DB_USER=postgres
DB_PASSWORD=
```

## What Was Created

When you first run the application:
1. ✅ Database `safai_chat_db` is created automatically (if it doesn't exist)
2. ✅ Required tables for chat history storage are created automatically
3. ✅ Chat history is now persistent across server restarts

## Verify It's Working

### Check Database Connection

```bash
python -c "from safai_rag_langgraph import app; print('Connected!')"
```

You should see:
```
✓ Database safai_chat_db already exists
✓ Connected to PostgreSQL database: safai_chat_db
✓ Database schema initialized
✓ Chat history will be stored persistently in PostgreSQL
```

### Check Tables Created

Connect to PostgreSQL and check:

```bash
psql -U postgres -d safai_chat_db
```

Then run:
```sql
\dt
```

You should see tables created by LangGraph for checkpointing (like `checkpoints`, `checkpoint_blobs`, etc.).

### Query Chat History

To view chat history directly from the database, you can query the checkpoint tables (though the structure is optimized for LangGraph's internal use).

**Better approach:** Use the API endpoint:
```bash
GET /sessions/{session_id}/history
```

## Troubleshooting

### Connection Failed

If you see:
```
⚠ Warning: Failed to connect to PostgreSQL
```

**Check:**
1. PostgreSQL is running: `pg_isready` or `brew services list` (if on Mac)
2. User has access: `psql -U postgres -l`
3. Database exists: `psql -U postgres -l | grep safai_chat_db`

### Start PostgreSQL (macOS)

```bash
brew services start postgresql@14
# or
brew services start postgresql@15
# or
brew services start postgresql@16
```

### Start PostgreSQL (Linux)

```bash
sudo systemctl start postgresql
# or
sudo service postgresql start
```

### Create Database Manually (if needed)

```bash
psql -U postgres
```

Then in psql:
```sql
CREATE DATABASE safai_chat_db;
\q
```

## Benefits

✅ **Persistent Storage** - Chat history survives server restarts
✅ **Production Ready** - Scalable and reliable
✅ **Queryable** - Can analyze chat history later
✅ **Automatic Setup** - Database and tables created automatically
✅ **Fallback Safety** - Falls back to memory if PostgreSQL unavailable

## Data Location

All chat history is stored in PostgreSQL tables in the `safai_chat_db` database. The data includes:
- Conversation messages
- Session state
- Checkpoint information
- Thread IDs for session management

## Backup Recommendations

For production, set up regular PostgreSQL backups:

```bash
# Backup database
pg_dump -U postgres safai_chat_db > backup_$(date +%Y%m%d).sql

# Restore database
psql -U postgres safai_chat_db < backup_YYYYMMDD.sql
```

## Next Steps

Your chat API is now production-ready with persistent storage! 🎉

- Chat history is automatically saved to PostgreSQL
- Sessions persist across server restarts
- All API endpoints work with the persistent storage
- No code changes needed - everything is automatic!
