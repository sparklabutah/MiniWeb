from app import create_app, db
app = create_app()
import json
SITE="banking"
with app.app_context():
    for coll in ["users","accounts","transactions","bills","payees","loans","cc_users","cc_transactions","cc_statements","cc_payments"]:
        try:
            rows = db.query(SITE, coll, limit=8)
            print(f"\n==== {coll} (showing {len(rows)}) count={db.count(SITE,coll)} ====")
            for r in rows:
                print(json.dumps(r, default=str))
        except Exception as e:
            print(coll, "ERR", repr(e))
