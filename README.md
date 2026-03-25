# SinkWave — Document Management System

A clean, channel-based document management platform built with Flask + MySQL.

---

## Project Structure

```
SinkWave/
├── app.py                   ← Flask backend (all routes & API)
├── schema.sql               ← MySQL database schema
├── requirements.txt         ← Python dependencies
├── templates/
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html       ← 3-tab main page
│   └── channel.html         ← Channel view
└── static/
    ├── css/style.css        ← All styles
    ├── js/dashboard.js      ← Dashboard logic
    ├── js/channel.js        ← Channel logic
    └── uploads/             ← Uploaded files (auto-created)
```

---

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up MySQL Database

Make sure MySQL is running, then run:

```bash
mysql -u root -p < schema.sql
```

### 3. Configure Database Connection

Open `app.py` and update the `DB_CONFIG` block near the top:

```python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'YOUR_MYSQL_PASSWORD',   # ← Change this
    'database': 'SinkWave'
}
```

### 4. Run the App

```bash
python app.py
```

Visit: **http://localhost:5000**

---

## Features

### Authentication

- Register with username, email, password
- Secure login with hashed passwords

### Dashboard (3 tabs)

1. **My Channels** — See all channels you've joined or created
2. **Search Channels** — Find any channel by its unique 8-character code; join instantly (public) or send a request (private)
3. **Create Channel** — Name your channel, set optional max members, choose Public or Private

### Inside a Channel

- **Documents tab** — Browse all uploaded files; react with 👍 ❤️ 🔥 ⭐ 👏; download files
- **Members tab** (admin only) — View all members; grant admin access to any member
- **Join Requests tab** (admin only, private channels) — Approve or reject pending join requests

### Admin Powers

- Upload any document file (PDF, Word, Excel, PowerPoint, TXT, images, ZIP, CSV)
- Give admin access to members
- Manage join requests for private channels

### File Types Supported

PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX, TXT, CSV, PNG, JPG, JPEG, ZIP

---

## Notes

- Max file upload size: 50 MB
- Channel codes are auto-generated 8-character unique identifiers
- Uploaded files are stored in `static/uploads/`
- For production, use a real secret key and consider using a cloud storage service for uploads
