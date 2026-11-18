import os
import statistics
from datetime import datetime
from collections import defaultdict, Counter
from typing import List

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

import models, schemas, auth
from database import engine, get_db

try:
    from google import genai
except ImportError:
    genai = None

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Personal Expense Tracker")

# Serve Frontend HTML & CSS
@app.get("/", response_class=FileResponse)
def serve_frontend():
    return FileResponse("index.html")

@app.get("/style.css", response_class=FileResponse)
def serve_css():
    return FileResponse("style.css")

@app.get("/icon.png", response_class=FileResponse)
def serve_icon():
    return FileResponse("icon.png")

# Register New User
@app.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_pwd = auth.get_password_hash(user.password)
    new_user = models.User(username=user.username, hashed_password=hashed_pwd)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# Login & Get JWT Token
@app.post("/login", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# Protected Routes (Require Authentication)
@app.post("/expenses/", response_model=schemas.ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(expense: schemas.ExpenseCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    db_expense = models.Expense(**expense.model_dump(), user_id=current_user.id)
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense

@app.get("/expenses/", response_model=List[schemas.ExpenseResponse])
def read_expenses(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    return db.query(models.Expense).filter(models.Expense.user_id == current_user.id).all()

@app.put("/expenses/{expense_id}", response_model=schemas.ExpenseResponse)
def update_expense(expense_id: int, updated_expense: schemas.ExpenseCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    expense_query = db.query(models.Expense).filter(models.Expense.id == expense_id, models.Expense.user_id == current_user.id)
    expense = expense_query.first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found or unauthorized")
    
    expense_query.update(updated_expense.model_dump(), synchronize_session=False)
    db.commit()
    return expense_query.first()

@app.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    expense = db.query(models.Expense).filter(models.Expense.id == expense_id, models.Expense.user_id == current_user.id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found or unauthorized")
    db.delete(expense)
    db.commit()
    return None

# AI Insights & Smart Daily Expense Detection Route
@app.get("/ai-insights")
def get_ai_insights(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    expenses = db.query(models.Expense).filter(models.Expense.user_id == current_user.id).all()

    if not expenses:
        return {
            "predicted_next_month": 0.0,
            "prediction_note": "Add at least 3 expenses to unlock monthly spending forecasts.",
            "patterns": ["No transaction history yet. Start adding daily expenses to detect habits."],
            "unusual_alerts": ["No anomalies detected yet."],
            "saving_suggestions": [
                "Track every small UPI and cash expense daily to build an accurate baseline.",
                "Set a realistic monthly budget limit at the top of your dashboard.",
                "Categorize your expenses properly to identify non-essential spending."
            ],
            "recurring_expenses": []
        }

    total_spent = sum(e.amount for e in expenses)
    category_amounts = defaultdict(list)
    payment_counts = defaultdict(int)
    title_groups = defaultdict(list)
    weekend_spend = 0.0
    micro_spends = []
    unique_dates = set()

    for e in expenses:
        category_amounts[e.category].append(e.amount)
        payment_counts[e.payment_mode] += 1
        unique_dates.add(e.date)
        norm_title = e.title.strip().lower()
        if norm_title:
            title_groups[norm_title].append(e)
        if e.amount <= 200:
            micro_spends.append(e.amount)
        try:
            dt = datetime.strptime(e.date, "%Y-%m-%d")
            if dt.weekday() >= 5:
                weekend_spend += e.amount
        except ValueError:
            pass

    # 0. Smart Daily / Recurring Expense Detection (for 1-Click Quick Add)
    daily_keywords = {
        "tea", "chai", "coffee", "milk", "doodh", "metro", "auto", "bus", "cab",
        "lunch", "breakfast", "dinner", "tiffin", "snacks", "water", "juice",
        "roti", "sabzi", "fruits", "petrol", "parking", "canteen"
    }
    recurring_candidates = []
    for norm_title, items in title_groups.items():
        count = len(items)
        items_sorted = sorted(items, key=lambda x: (x.date, x.id), reverse=True)
        latest = items_sorted[0]
        # Most frequent amount for this expense
        common_amount = Counter(i.amount for i in items).most_common(1)[0][0]
        is_keyword_daily = any(word in norm_title.split() or word in norm_title for word in daily_keywords)

        if count >= 2 or is_keyword_daily:
            recurring_candidates.append({
                "title": latest.title.strip(),
                "amount": common_amount,
                "category": latest.category,
                "payment_mode": latest.payment_mode,
                "count": count,
                "label": f"{count}x logged" if count >= 2 else "Daily habit",
                "latest_date": latest.date
            })

    recurring_candidates.sort(key=lambda x: (x["count"], x["latest_date"]), reverse=True)
    recurring_expenses = [
        {
            "title": item["title"],
            "amount": item["amount"],
            "category": item["category"],
            "payment_mode": item["payment_mode"],
            "label": item["label"]
        }
        for item in recurring_candidates[:6]
    ]

    # 1. Next Month Expense Prediction
    active_days = max(len(unique_dates), 1)
    daily_avg = total_spent / active_days
    sorted_expenses = sorted(expenses, key=lambda x: x.date)
    
    trend_multiplier = 1.0
    if len(sorted_expenses) >= 4:
        mid = len(sorted_expenses) // 2
        first_half_avg = sum(e.amount for e in sorted_expenses[:mid]) / mid
        second_half_avg = sum(e.amount for e in sorted_expenses[mid:]) / (len(sorted_expenses) - mid)
        if first_half_avg > 0:
            ratio = second_half_avg / first_half_avg
            trend_multiplier = max(0.85, min(1.25, ratio))

    predicted_next_month = round(daily_avg * 30 * trend_multiplier, 2)
    trend_direction = "upward" if trend_multiplier > 1.03 else ("downward" if trend_multiplier < 0.97 else "steady")
    prediction_note = f"Based on ₹{daily_avg:.0f}/day average across {active_days} active day(s) with a {trend_direction} trend."

    # 2. Unusual Spending Alerts
    unusual_alerts = []
    for e in expenses:
        cat_list = category_amounts[e.category]
        if len(cat_list) >= 3:
            mean_val = statistics.mean(cat_list)
            stdev_val = statistics.stdev(cat_list)
            if stdev_val > 0 and e.amount > (mean_val + 1.5 * stdev_val) and e.amount > (mean_val * 1.7):
                multiplier = round(e.amount / mean_val, 1)
                unusual_alerts.append(
                    f"High {e.category} Spend: ₹{e.amount:.0f} on '{e.title}' ({e.date}) is {multiplier}x your average ₹{mean_val:.0f}."
                )
    if not unusual_alerts:
        unusual_alerts.append("All transactions look normal. No unusual spending spikes detected.")

    # 3. Spending Pattern Detection
    patterns = []
    if total_spent > 0:
        weekend_pct = (weekend_spend / total_spent) * 100
        if weekend_pct >= 40:
            patterns.append(f"Weekend Surge: {weekend_pct:.0f}% of your total money (₹{weekend_spend:.0f}) is spent on weekends.")
        else:
            patterns.append(f"Weekday Focus: {100 - weekend_pct:.0f}% of your spending happens on weekdays (Mon–Fri).")

    top_mode = max(payment_counts.items(), key=lambda x: x[1])
    mode_pct = (top_mode[1] / len(expenses)) * 100
    patterns.append(f"Preferred Payment Mode: {top_mode[0]} is used for {mode_pct:.0f}% of your transactions.")

    if len(micro_spends) >= 3:
        patterns.append(f"Frequent Micro-Spends: {len(micro_spends)} small purchases (≤₹200) added up to ₹{sum(micro_spends):.0f}.")

    # 4. AI-Based Saving Suggestions
    cat_summary = {cat: round(sum(vals), 2) for cat, vals in category_amounts.items()}
    top_category = max(cat_summary.items(), key=lambda x: x[1])

    saving_suggestions = []
    api_key = os.environ.get("GEMINI_API_KEY")

    if genai and api_key:
        try:
            client = genai.Client(api_key=api_key)
            prompt = (
                f"You are a concise personal finance advisor for an Indian user (currency ₹). "
                f"Analyze this expense summary: Total Spent = ₹{total_spent:.2f}, "
                f"Category Breakdown = {cat_summary}, Predicted Next Month = ₹{predicted_next_month:.2f}, "
                f"Patterns = {patterns}. "
                f"Give exactly 3 short, practical, personalized money-saving tips (max 18 words each). "
                f"Return only the 3 tips separated by newlines, without numbering, bullets, or bold markdown."
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            if response and response.text:
                lines = [line.strip(" -•*123.") for line in response.text.strip().split("\n") if line.strip()]
                saving_suggestions = lines[:3]
        except Exception as exc:
            print("AI fallback triggered:", exc)

    if not saving_suggestions:
        saving_suggestions = [
            f"Cut {top_category[0]} expenses by 15% next month to save around ₹{top_category[1] * 0.15:.0f}.",
            f"Set a weekly spending cap of ₹{predicted_next_month / 4:.0f} to stay ahead of your predicted monthly spend.",
            "Batch small daily UPI purchases into a planned weekly list to curb impulse spending."
        ]

    return {
        "predicted_next_month": predicted_next_month,
        "prediction_note": prediction_note,
        "patterns": patterns,
        "unusual_alerts": unusual_alerts[:3],
        "saving_suggestions": saving_suggestions,
        "recurring_expenses": recurring_expenses
    }