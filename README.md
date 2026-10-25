# 💰 Personal Expense Tracker

A full-stack, secure, and feature-rich **Personal Expense Tracker** web application built with **FastAPI**, **SQLAlchemy (SQLite)**, and modern vanilla **HTML5/CSS3/JavaScript**.

It features JWT-based user authentication, multi-user data isolation, real-time analytics with Chart.js, budget tracking, advanced filtering, persistent dual-theme styling, and one-click data exports (CSV & PDF).

---

## ✨ Features

- 🔐 **User Authentication & Security:** JWT (JSON Web Tokens) authentication with `bcrypt` password hashing. Each user gets a secure, private dashboard.
- 🎨 **Dual Aesthetics (Theme Switcher):**
  - **Dark Mode:** Cyber Neon (Jet Black, Cerulean & Neon Rose)
  - **Light Mode:** Ice Silver, Deep Aubergine & Marigold
  - Persistent theme selection saved via `localStorage`.
- 📊 **Real-Time Visual Analytics:**
  - **Category Analytics:** Interactive Doughnut Chart showing category-wise spending.
  - **Spending Trend:** Interactive Line Chart tracking daily spending trends.
- 💡 **Quick Insights Badges:** Instant cards showing Highest Expense, Top Spending Category, and Total Transaction Count.
- 🎯 **Monthly Budget Progress Tracker:** Set a monthly spending limit and monitor usage with a dynamic percentage progress bar.
- 🔍 **Advanced Filtering & Search:** Search expenses by title/notes, filter by category, or set custom Start and End date ranges.
- 📁 **Data Exporting:**
  - **Export CSV:** Instant download of all transactions for spreadsheets.
  - **Export PDF:** Clean, print-formatted PDF report generation.

---

## 🛠️ Tech Stack

- **Backend:** FastAPI, Python 3.10+
- **Database & ORM:** SQLite, SQLAlchemy
- **Authentication:** PyJWT / `python-jose`, `bcrypt`
- **Frontend:** HTML5, CSS3 (CSS Variables & Grid/Flexbox), JavaScript (ES6 Fetch API)
- **Data Visualization:** Chart.js

---

## 📂 Project Structure

```text
expense_tracker/
│
├── database.py       # SQLite engine and SessionLocal setup
├── models.py         # SQLAlchemy database models (User, Expense)
├── schemas.py        # Pydantic schemas for data validation
├── auth.py           # Password hashing & JWT token handling
├── main.py           # FastAPI routes & static files serving
├── index.html        # Single-page dynamic dashboard UI
├── style.css         # Modern Cyber Neon & Light mode styles
└── expenses.db       # SQLite database (Auto-generated)
```
