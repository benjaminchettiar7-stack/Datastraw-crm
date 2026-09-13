from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def init_db():
  conn = sqlite3.connect("crm.db")
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE,
            customer_name TEXT,
            customer_email TEXT,
            subject TEXT,
            description TEXT,
            status TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT,
            note_text TEXT,
            created_at TEXT
        )
    """)
  conn.commit()
  conn.close()


init_db()


class TicketCreate(BaseModel):
  customer_name: str
  customer_email: str
  subject: str
  description: str


class TicketUpdate(BaseModel):
  status: str
  notes: str | None = None


@app.post("/api/tickets")
def create_ticket(ticket: TicketCreate):
  conn = sqlite3.connect("crm.db")
  cursor = conn.cursor()

  cursor.execute("SELECT COUNT(*) FROM tickets")
  count = cursor.fetchone()[0]
  ticket_id = f"TKT-{str(count + 1).zfill(3)}"

  now = datetime.utcnow().isoformat()
  status = "Open"

  cursor.execute(
      """
        INSERT INTO tickets (ticket_id, customer_name, customer_email, subject, description, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
      (
          ticket_id,
          ticket.customer_name,
          ticket.customer_email,
          ticket.subject,
          ticket.description,
          status,
          now,
          now,
      ),
  )
  conn.commit()
  conn.close()
  return {"ticket_id": ticket_id, "created_at": now}


@app.get("/api/tickets")
def get_tickets(status: str | None = None, search: str | None = None):
  conn = sqlite3.connect("crm.db")
  cursor = conn.cursor()

  query = "SELECT ticket_id, customer_name, subject, status, created_at FROM tickets WHERE 1=1"
  params = []

  if status:
    query += " AND status = ?"
    params.append(status)

  if search:
    query += " AND (customer_name LIKE ? OR customer_email LIKE ? OR ticket_id LIKE ? OR description LIKE ?)"
    search_term = f"%{search}%"
    params.extend([search_term, search_term, search_term, search_term])

  cursor.execute(query, params)
  rows = cursor.fetchall()
  conn.close()

  tickets = []
  for row in rows:
    tickets.append({
        "ticket_id": row[0],
        "customer_name": row[1],
        "subject": row[2],
        "status": row[3],
        "created_at": row[4],
    })
  return tickets


@app.get("/api/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
  conn = sqlite3.connect("crm.db")
  cursor = conn.cursor()

  cursor.execute(
      "SELECT ticket_id, customer_name, customer_email, subject, description,"
      " status, created_at FROM tickets WHERE ticket_id = ?",
      (ticket_id,),
  )
  row = cursor.fetchone()

  if not row:
    conn.close()
    raise HTTPException(status_code=404, detail="Ticket not found")

  cursor.execute(
      "SELECT note_text, created_at FROM notes WHERE ticket_id = ?",
      (ticket_id,),
  )
  notes_rows = cursor.fetchall()
  notes = [{"note_text": n[0], "created_at": n[1]} for n in notes_rows]
  conn.close()

  return {
      "ticket_id": row[0],
      "customer_name": row[1],
      "customer_email": row[2],
      "subject": row[3],
      "description": row[4],
      "status": row[5],
      "created_at": row[6],
      "notes": notes,
  }


@app.put("/api/tickets/{ticket_id}")
def update_ticket(ticket_id: str, update: TicketUpdate):
  conn = sqlite3.connect("crm.db")
  cursor = conn.cursor()

  cursor.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,))
  if not cursor.fetchone():
    conn.close()
    raise HTTPException(status_code=404, detail="Ticket not found")

  now = datetime.utcnow().isoformat()
  cursor.execute(
      "UPDATE tickets SET status = ?, updated_at = ? WHERE ticket_id = ?",
      (update.status, now, ticket_id),
  )

  if update.notes:
    cursor.execute(
        "INSERT INTO notes (ticket_id, note_text, created_at) VALUES (?, ?, ?)",
        (ticket_id, update.notes, now),
    )

  conn.commit()
  conn.close()
  return {"success": True, "updated_at": now}
