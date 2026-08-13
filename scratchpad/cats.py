from app import create_app, db
app = create_app()
with app.app_context():
    print("BANK CATS u1:", [r["category"] for r in db.execute("SELECT DISTINCT category FROM banking_transactions WHERE user_id=1 ORDER BY category")])
    print("BANK TYPES:", [r["type"] for r in db.execute("SELECT DISTINCT type FROM banking_transactions")])
    print("CC CATS u1:", [r["category"] for r in db.execute("SELECT DISTINCT category FROM banking_cc_transactions WHERE user_id=1 ORDER BY category")])
    print("CC STATUS:", [r["status"] for r in db.execute("SELECT DISTINCT status FROM banking_cc_transactions")])
    print("BILL CATS:", [r["category"] for r in db.execute("SELECT DISTINCT category FROM banking_bills")])
    print("PAYEE CATS:", [r["category"] for r in db.execute("SELECT DISTINCT category FROM banking_payees")])
    print("LOAN TYPES:", [r["type"] for r in db.execute("SELECT DISTINCT type FROM banking_loans")])
    print("PAYEES u1:", [ (r["name"],r["nickname"],r["category"]) for r in db.execute("SELECT name,nickname,category FROM banking_payees WHERE user_id=1")])
    print("BILLS u1 due:", [ (r["payee_name"],r["amount"],r["due_date"],r["status"]) for r in db.execute("SELECT payee_name,amount,due_date,status FROM banking_bills WHERE user_id=1 AND status='due'")])
