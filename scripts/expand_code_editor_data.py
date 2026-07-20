"""Expand code-editor-execution (CodeRunner) base data.

The online IDE ships with 25 snippets / 5 users. Adds deterministic (seeded)
synthetic Python snippets across new and existing categories (conversions,
math, strings, regex, datetime, data-structures, basics, oop, parsing,
itertools, algorithms) plus extra Meridian Systems user accounts.

Scale note: the snippet gallery (/) renders ALL snippets unpaginated and the
users table is fully loaded/rewritten by most routes, so this site cannot
plausibly carry 5000 rows. Ceiling used: <=~450 snippets (gallery stays under
the ~500-rows-per-page cap) and <100 users (routes.py loads the whole table).

Task-safety: new rows never contain the substrings that saved annotation
tasks search for (sort, caesar, cipher, fibonacci, matrix, rotat-, transpose,
maze, path, planning, hash, sum, sequence, leetcode, trail, graph, route) in
any column, never use category "sorting" or "projects", and implement no
sorting algorithm. Every snippet is short, harmless, deterministic Python
that passes the site's dangerous-import check; expected_output is computed by
actually running each snippet with the same interpreter the site uses
(python3 -c), twice with different PYTHONHASHSEED to prove determinism.

Insert-only; inserted ids recorded under data/backups/ for rollback.

Usage: python scripts/expand_code_editor_data.py [--dry-run]
"""
import json
import random
import re
import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
rng = random.Random(20260720)

# Substrings (case-insensitive) that must never appear in any new row —
# they would change the result sets of searches used by saved tasks.
FORBID = ["sort", "caesar", "cipher", "fibonacci", "matrix", "rotat",
          "transpose", "maze", "path", "planning", "hash", "sum",
          "sequence", "leetcode", "trail", "graph", "route "]
# Site's dangerous-code patterns (mirror of routes._check_dangerous)
DANGEROUS = ["import os", "import sys", "import io", "import subprocess",
             "open(", "eval(", "exec(", "input(", "sorted(", ".sort("]

SNIPS = []
_titles = set()


def S(title, cat, diff, desc, code):
    code = textwrap.dedent(code).strip("\n")
    low = f"{title}\n{desc}\n{cat}\n{code}".lower()
    for w in FORBID:
        assert w not in low, f"forbidden {w!r} in {title!r}"
    for w in DANGEROUS:
        assert w not in code, f"dangerous {w!r} in {title!r}"
    assert title not in _titles, f"dup title {title!r}"
    _titles.add(title)
    SNIPS.append({"title": title, "language": "python", "code": code,
                  "description": desc, "category": cat, "difficulty": diff,
                  "expected_output": ""})


# ---------------------------------------------------------------------------
# 1. Unit converters (category: conversions)
# ---------------------------------------------------------------------------
CONV = [
    ("Miles", "Kilometers", "mi", "km", "v * 1.60934", [1, 5, 26.2, 100], "distances"),
    ("Kilometers", "Miles", "km", "mi", "v / 1.60934", [1, 10, 42.195, 200], "distances"),
    ("Celsius", "Fahrenheit", "C", "F", "v * 9 / 5 + 32", [0, 21.5, 37, 100], "temperatures"),
    ("Fahrenheit", "Celsius", "F", "C", "(v - 32) * 5 / 9", [32, 72, 98.6, 212], "temperatures"),
    ("Celsius", "Kelvin", "C", "K", "v + 273.15", [0, 25, 100], "temperatures"),
    ("Kelvin", "Celsius", "K", "C", "v - 273.15", [273.15, 300, 373.15], "temperatures"),
    ("Kilograms", "Pounds", "kg", "lb", "v * 2.20462", [1, 5, 70, 100], "weights"),
    ("Pounds", "Kilograms", "lb", "kg", "v / 2.20462", [1, 10, 154, 220], "weights"),
    ("Grams", "Ounces", "g", "oz", "v / 28.3495", [28, 100, 500], "weights"),
    ("Ounces", "Grams", "oz", "g", "v * 28.3495", [1, 8, 16], "weights"),
    ("Meters", "Feet", "m", "ft", "v * 3.28084", [1, 10, 100, 8848], "lengths"),
    ("Feet", "Meters", "ft", "m", "v / 3.28084", [1, 6, 100, 29032], "lengths"),
    ("Inches", "Centimeters", "in", "cm", "v * 2.54", [1, 12, 36], "lengths"),
    ("Centimeters", "Inches", "cm", "in", "v / 2.54", [2.54, 30, 100], "lengths"),
    ("Liters", "US Gallons", "L", "gal", "v / 3.78541", [1, 10, 50], "volumes"),
    ("US Gallons", "Liters", "gal", "L", "v * 3.78541", [1, 5, 15], "volumes"),
    ("Miles per Hour", "Kilometers per Hour", "mph", "km/h", "v * 1.60934", [30, 60, 100], "speeds"),
    ("Kilometers per Hour", "Miles per Hour", "km/h", "mph", "v / 1.60934", [50, 100, 130], "speeds"),
    ("Knots", "Miles per Hour", "kn", "mph", "v * 1.15078", [10, 20, 35], "speeds"),
    ("Acres", "Hectares", "ac", "ha", "v * 0.404686", [1, 40, 640], "land areas"),
    ("Hectares", "Acres", "ha", "ac", "v / 0.404686", [1, 10, 100], "land areas"),
    ("PSI", "Kilopascals", "psi", "kPa", "v * 6.89476", [14.7, 32, 100], "pressures"),
    ("Atmospheres", "PSI", "atm", "psi", "v * 14.6959", [1, 2, 5.5], "pressures"),
    ("Kilocalories", "Kilojoules", "kcal", "kJ", "v * 4.184", [100, 500, 2000], "energy values"),
    ("Degrees", "Radians", "deg", "rad", "v * 3.141592653589793 / 180", [30, 90, 180, 360], "angles"),
    ("Radians", "Degrees", "rad", "deg", "v * 180 / 3.141592653589793", [1, 1.5708, 3.1416], "angles"),
    ("Nautical Miles", "Kilometers", "nmi", "km", "v * 1.852", [1, 100, 500], "distances"),
    ("Yards", "Meters", "yd", "m", "v * 0.9144", [1, 100, 440], "lengths"),
    ("Meters", "Yards", "m", "yd", "v / 0.9144", [1, 91.44, 400], "lengths"),
    ("Stone", "Kilograms", "st", "kg", "v * 6.35029", [1, 10, 12.5], "weights"),
    ("Cups", "Milliliters", "cup", "mL", "v * 236.588", [0.5, 1, 2], "cooking measures"),
    ("Milliliters", "Cups", "mL", "cup", "v / 236.588", [100, 250, 500], "cooking measures"),
    ("Tablespoons", "Milliliters", "tbsp", "mL", "v * 14.7868", [1, 3, 8], "cooking measures"),
    ("Teaspoons", "Milliliters", "tsp", "mL", "v * 4.92892", [1, 2, 6], "cooking measures"),
    ("Fluid Ounces", "Milliliters", "fl_oz", "mL", "v * 29.5735", [1, 8, 12], "volumes"),
    ("Pints", "Liters", "pt", "L", "v * 0.473176", [1, 2, 8], "volumes"),
    ("Quarts", "Liters", "qt", "L", "v * 0.946353", [1, 4, 10], "volumes"),
    ("Square Feet", "Square Meters", "sq_ft", "sq_m", "v * 0.092903", [100, 750, 2000], "floor areas"),
    ("Square Meters", "Square Feet", "sq_m", "sq_ft", "v / 0.092903", [10, 65, 200], "floor areas"),
    ("Horsepower", "Watts", "hp", "W", "v * 745.7", [1, 150, 400], "power ratings"),
    ("Watts", "Horsepower", "W", "hp", "v / 745.7", [746, 1500, 5000], "power ratings"),
    ("Megabytes", "Gigabytes", "MB", "GB", "v / 1024", [512, 2048, 10240], "storage sizes"),
    ("Gigabytes", "Megabytes", "GB", "MB", "v * 1024", [0.5, 2, 16], "storage sizes"),
    ("Carats", "Grams", "ct", "g", "v * 0.2", [0.5, 1, 5], "gem weights"),
    ("Days", "Hours", "d", "h", "v * 24", [1, 7, 30], "durations"),
    ("Weeks", "Days", "wk", "d", "v * 7", [1, 4, 52], "durations"),
]

for a, b, ua, ub, expr, samples, noun in CONV:
    fa = a.lower().replace(" ", "_").replace("-", "_")
    fb = b.lower().replace(" ", "_").replace("-", "_")
    body = (
        f"def {fa}_to_{fb}(v):\n"
        f"    return {expr}\n\n"
        f"for v in {samples}:\n"
        f"    print(f\"{{v}} {ua} = {{{fa}_to_{fb}(v):.2f}} {ub}\")\n"
    )
    S(f"{a} to {b} Converter", "conversions", "easy",
      f"Convert {noun} from {a.lower()} to {b.lower()} using the standard factor.",
      body)

# ---------------------------------------------------------------------------
# 2. Geometry (category: math)
# ---------------------------------------------------------------------------
GEO = [
    ("Rectangle Area and Perimeter", "easy",
     "Compute the area and perimeter of a rectangle from width and height.", """
     def rect(w, h):
         return w * h, 2 * (w + h)

     for w, h in [(3, 4), (5.5, 2), (10, 10)]:
         area, per = rect(w, h)
         print(f"{w} x {h}: area={area}, perimeter={per}")
     """),
    ("Circle Area and Circumference", "easy",
     "Compute the area and circumference of a circle from its radius.", """
     import math

     for r in [1, 2.5, 10]:
         print(f"r={r}: area={math.pi * r ** 2:.3f}, circumference={2 * math.pi * r:.3f}")
     """),
    ("Triangle Area with Heron's Formula", "medium",
     "Compute a triangle's area from its three side lengths using Heron's formula.", """
     import math

     def heron(a, b, c):
         s = (a + b + c) / 2
         return math.sqrt(s * (s - a) * (s - b) * (s - c))

     for sides in [(3, 4, 5), (7, 8, 9), (6, 6, 6)]:
         print(f"sides {sides}: area = {heron(*sides):.3f}")
     """),
    ("Trapezoid Area Calculator", "easy",
     "Compute the area of a trapezoid from its two bases and height.", """
     def trapezoid_area(b1, b2, h):
         return (b1 + b2) / 2 * h

     for b1, b2, h in [(3, 5, 4), (10, 6, 2.5)]:
         print(f"bases {b1},{b2} height {h}: area = {trapezoid_area(b1, b2, h)}")
     """),
    ("Regular Polygon Area", "medium",
     "Compute the area of a regular polygon from side count and side length.", """
     import math

     def polygon_area(n, side):
         return n * side ** 2 / (4 * math.tan(math.pi / n))

     for n, side in [(5, 2), (6, 2), (8, 1.5)]:
         print(f"{n}-gon with side {side}: area = {polygon_area(n, side):.3f}")
     """),
    ("Ellipse Area Calculator", "easy",
     "Compute the area of an ellipse from its semi-axes.", """
     import math

     for a, b in [(3, 2), (5, 5), (10, 1)]:
         print(f"semi-axes {a},{b}: area = {math.pi * a * b:.3f}")
     """),
    ("Sphere Volume and Surface", "easy",
     "Compute the volume and surface area of a sphere from its radius.", """
     import math

     for r in [1, 3, 6.371]:
         vol = 4 / 3 * math.pi * r ** 3
         surf = 4 * math.pi * r ** 2
         print(f"r={r}: volume={vol:.3f}, surface={surf:.3f}")
     """),
    ("Cylinder Volume Calculator", "easy",
     "Compute the volume of a cylinder from radius and height.", """
     import math

     def cylinder(r, h):
         return math.pi * r ** 2 * h

     for r, h in [(2, 5), (1.5, 10), (4, 4)]:
         print(f"r={r}, h={h}: volume = {cylinder(r, h):.3f}")
     """),
    ("Cone Volume Calculator", "easy",
     "Compute the volume of a cone from radius and height.", """
     import math

     for r, h in [(3, 4), (2, 9), (5, 12)]:
         print(f"r={r}, h={h}: volume = {math.pi * r ** 2 * h / 3:.3f}")
     """),
    ("Cube and Box Volume", "easy",
     "Compute volumes of a cube and a rectangular box.", """
     def box_volume(w, d, h):
         return w * d * h

     print(f"cube side 3: {box_volume(3, 3, 3)}")
     print(f"box 2x3x4: {box_volume(2, 3, 4)}")
     print(f"box 1.5x2x8: {box_volume(1.5, 2, 8)}")
     """),
    ("Square Pyramid Volume", "easy",
     "Compute the volume of a square pyramid from base side and height.", """
     for base, h in [(6, 9), (2, 3), (230, 146)]:
         print(f"base {base}, height {h}: volume = {base ** 2 * h / 3:.1f}")
     """),
    ("Circle Sector Area and Arc", "medium",
     "Compute the sector area and arc length for a central angle in degrees.", """
     import math

     def sector(r, deg):
         rad = math.radians(deg)
         return r ** 2 * rad / 2, r * rad

     for r, deg in [(5, 90), (3, 45), (10, 270)]:
         area, arc = sector(r, deg)
         print(f"r={r}, angle={deg}: area={area:.3f}, arc={arc:.3f}")
     """),
    ("Annulus Area Calculator", "easy",
     "Compute the area of the ring between two concentric circles.", """
     import math

     def annulus(outer, inner):
         return math.pi * (outer ** 2 - inner ** 2)

     for outer, inner in [(5, 3), (10, 9), (2.5, 1)]:
         print(f"R={outer}, r={inner}: area = {annulus(outer, inner):.3f}")
     """),
    ("Right Triangle Checker", "easy",
     "Check whether three side lengths form a right triangle.", """
     def is_right(a, b, c):
         x, y, z = min(a, b, c), a + b + c - min(a, b, c) - max(a, b, c), max(a, b, c)
         return abs(x * x + y * y - z * z) < 1e-9

     for sides in [(3, 4, 5), (5, 12, 13), (4, 5, 6)]:
         print(f"{sides}: right triangle = {is_right(*sides)}")
     """),
    ("Distance Between Two Points", "easy",
     "Compute the Euclidean distance between two points in the plane.", """
     import math

     def dist(p, q):
         return math.hypot(p[0] - q[0], p[1] - q[1])

     pairs = [((0, 0), (3, 4)), ((1, 1), (4, 5)), ((-2, 3), (2, 0))]
     for p, q in pairs:
         print(f"{p} -> {q}: distance = {dist(p, q)}")
     """),
    ("Slope and Line Equation", "easy",
     "Compute the slope and intercept of the line through two points.", """
     def line(p, q):
         m = (q[1] - p[1]) / (q[0] - p[0])
         b = p[1] - m * p[0]
         return m, b

     for p, q in [((0, 1), (2, 5)), ((1, 1), (3, 0))]:
         m, b = line(p, q)
         print(f"through {p} and {q}: y = {m:.2f}x + {b:.2f}")
     """),
]
for title, diff, desc, code in GEO:
    S(title, "math", diff, desc, code)

# ---------------------------------------------------------------------------
# 3. Finance & everyday calculators (category: math)
# ---------------------------------------------------------------------------
FIN = [
    ("Simple Interest Calculator", "easy",
     "Compute simple interest for a principal, rate, and term.", """
     def simple_interest(principal, rate, years):
         return principal * rate / 100 * years

     for p, r, y in [(1000, 5, 3), (2500, 3.5, 10)]:
         print(f"${p} at {r}% for {y}y -> interest ${simple_interest(p, r, y):.2f}")
     """),
    ("Compound Interest Calculator", "easy",
     "Compute the future value of an investment with yearly compounding.", """
     def future_value(principal, rate, years):
         return principal * (1 + rate / 100) ** years

     for p, r, y in [(1000, 5, 10), (5000, 7, 30)]:
         print(f"${p} at {r}% for {y}y -> ${future_value(p, r, y):.2f}")
     """),
    ("Monthly Loan Payment", "medium",
     "Compute the fixed monthly payment for an amortized loan.", """
     def monthly_payment(principal, annual_rate, years):
         r = annual_rate / 100 / 12
         n = years * 12
         return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)

     for p, rate, y in [(250000, 6.5, 30), (20000, 4.9, 5)]:
         print(f"${p} at {rate}% over {y}y -> ${monthly_payment(p, rate, y):.2f}/mo")
     """),
    ("Tip Calculator", "easy",
     "Compute tip amounts and totals for a restaurant bill.", """
     bill = 84.50
     for pct in [15, 18, 20]:
         tip = bill * pct / 100
         print(f"{pct}% tip on ${bill:.2f}: tip ${tip:.2f}, total ${bill + tip:.2f}")
     """),
    ("Bill Splitter", "easy",
     "Split a bill evenly among diners, rounding to whole cents.", """
     def split(total, people):
         share = round(total / people, 2)
         return share

     for total, people in [(120.00, 4), (87.35, 3), (45.10, 6)]:
         print(f"${total:.2f} among {people}: ${split(total, people):.2f} each")
     """),
    ("Sales Tax Calculator", "easy",
     "Add sales tax to a list of item prices.", """
     TAX_RATE = 8.25
     prices = [19.99, 4.50, 129.00]
     for p in prices:
         taxed = p * (1 + TAX_RATE / 100)
         print(f"${p:.2f} -> ${taxed:.2f} with {TAX_RATE}% tax")
     """),
    ("Discount Price Calculator", "easy",
     "Apply percentage discounts to original prices.", """
     def discounted(price, pct):
         return price * (1 - pct / 100)

     for price, pct in [(80, 25), (199.99, 10), (45, 50)]:
         print(f"${price} at {pct}% off -> ${discounted(price, pct):.2f}")
     """),
    ("Percent Change Calculator", "easy",
     "Compute the percent change between old and new values.", """
     def pct_change(old, new):
         return (new - old) / old * 100

     for old, new in [(50, 65), (120, 90), (8, 8.4)]:
         print(f"{old} -> {new}: {pct_change(old, new):+.1f}%")
     """),
    ("BMI Calculator", "easy",
     "Compute body mass index from weight and height with a category label.", """
     def bmi(kg, meters):
         return kg / meters ** 2

     def label(b):
         if b < 18.5:
             return "underweight"
         if b < 25:
             return "normal"
         if b < 30:
             return "overweight"
         return "obese"

     for kg, m in [(70, 1.75), (95, 1.8), (50, 1.6)]:
         b = bmi(kg, m)
         print(f"{kg}kg / {m}m: BMI {b:.1f} ({label(b)})")
     """),
    ("Unit Price Comparator", "easy",
     "Compare unit prices of two package sizes to find the better deal.", """
     def unit_price(price, units):
         return price / units

     a = ("Brand A", 4.99, 12)
     b = ("Brand B", 7.49, 20)
     for name, price, units in [a, b]:
         print(f"{name}: ${unit_price(price, units):.3f} per unit")
     better = a if unit_price(a[1], a[2]) < unit_price(b[1], b[2]) else b
     print(f"Better deal: {better[0]}")
     """),
    ("Savings Goal Estimator", "medium",
     "Count the months needed to reach a savings goal with interest.", """
     def months_to_goal(goal, monthly, annual_rate):
         balance, months = 0.0, 0
         r = annual_rate / 100 / 12
         while balance < goal and months < 1200:
             balance = balance * (1 + r) + monthly
             months += 1
         return months

     for goal, monthly, rate in [(10000, 250, 4.0), (5000, 100, 2.5)]:
         print(f"${goal} at ${monthly}/mo, {rate}%: {months_to_goal(goal, monthly, rate)} months")
     """),
    ("Break-Even Point Calculator", "easy",
     "Compute how many units must be sold to cover fixed costs.", """
     import math

     def break_even(fixed, price, variable):
         return math.ceil(fixed / (price - variable))

     for fixed, price, var in [(12000, 25, 10), (500, 8, 3.5)]:
         print(f"fixed ${fixed}, price ${price}, cost ${var}: {break_even(fixed, price, var)} units")
     """),
    ("Markup Percentage Calculator", "easy",
     "Compute selling price from cost and markup percentage.", """
     def with_markup(cost, pct):
         return cost * (1 + pct / 100)

     for cost, pct in [(12.50, 40), (200, 15), (3.20, 120)]:
         print(f"cost ${cost} + {pct}% markup -> ${with_markup(cost, pct):.2f}")
     """),
    ("Fuel Cost Estimator", "easy",
     "Estimate fuel cost for a trip from distance, efficiency, and price.", """
     def trip_cost(km, l_per_100km, price_per_l):
         liters = km * l_per_100km / 100
         return liters * price_per_l

     for km, eff, price in [(450, 7.2, 1.65), (1200, 9.5, 1.48)]:
         print(f"{km} km at {eff} L/100km: ${trip_cost(km, eff, price):.2f}")
     """),
]
for title, diff, desc, code in FIN:
    S(title, "math", diff, desc, code)

# ---------------------------------------------------------------------------
# 4. Number theory & digits (category: math)
# ---------------------------------------------------------------------------
NUM = [
    ("Prime Checker", "easy",
     "Check whether a value is prime using trial division.", """
     def is_prime(n):
         if n < 2:
             return False
         i = 2
         while i * i <= n:
             if n % i == 0:
                 return False
             i += 1
         return True

     for n in [2, 15, 17, 91, 97]:
         print(f"{n}: prime = {is_prime(n)}")
     """),
    ("Prime Checker (6k plus or minus 1)", "medium",
     "Faster primality test that only tries divisors of the form 6k +/- 1.", """
     def is_prime(n):
         if n < 2:
             return False
         if n < 4:
             return True
         if n % 2 == 0 or n % 3 == 0:
             return False
         i = 5
         while i * i <= n:
             if n % i == 0 or n % (i + 2) == 0:
                 return False
             i += 6
         return True

     for n in [97, 561, 7919, 100003]:
         print(f"{n}: prime = {is_prime(n)}")
     """),
    ("Perfect Number Checker", "easy",
     "Check whether a value equals the total of its proper divisors.", """
     def is_perfect(n):
         total = 0
         for d in range(1, n):
             if n % d == 0:
                 total += d
         return total == n

     for n in [6, 28, 100, 496]:
         print(f"{n}: perfect = {is_perfect(n)}")
     """),
    ("Armstrong Value Checker", "easy",
     "Check whether a value equals the total of its digits raised to the digit count.", """
     def is_armstrong(n):
         digits = str(n)
         total = 0
         for d in digits:
             total += int(d) ** len(digits)
         return total == n

     for n in [153, 370, 9474, 100]:
         print(f"{n}: Armstrong = {is_armstrong(n)}")
     """),
    ("Palindrome Integer Checker", "easy",
     "Check whether an integer reads the same in both directions.", """
     def is_palindrome_int(n):
         s = str(n)
         return s == s[::-1]

     for n in [121, 1331, 1234, 45654]:
         print(f"{n}: palindrome = {is_palindrome_int(n)}")
     """),
    ("Digit Total Calculator", "easy",
     "Add up the decimal digits of an integer.", """
     def digit_total(n):
         total = 0
         while n:
             total += n % 10
             n //= 10
         return total

     for n in [1234, 999, 100000, 4728]:
         print(f"{n} -> {digit_total(n)}")
     """),
    ("Digital Root Calculator", "easy",
     "Repeatedly add digits until a single digit remains.", """
     def digital_root(n):
         while n > 9:
             total = 0
             while n:
                 total += n % 10
                 n //= 10
             n = total
         return n

     for n in [942, 132189, 493193, 9]:
         print(f"{n} -> {digital_root(n)}")
     """),
    ("Reverse an Integer", "easy",
     "Reverse the digits of an integer, keeping the sign.", """
     def reverse_int(n):
         sign = -1 if n < 0 else 1
         return sign * int(str(abs(n))[::-1])

     for n in [1234, -567, 1200, 5]:
         print(f"{n} -> {reverse_int(n)}")
     """),
    ("Decimal to Binary (manual)", "easy",
     "Convert a decimal integer to binary with repeated division.", """
     def to_binary(n):
         if n == 0:
             return "0"
         bits = ""
         while n:
             bits = str(n % 2) + bits
             n //= 2
         return bits

     for n in [5, 10, 255, 1024]:
         print(f"{n} -> {to_binary(n)}")
     """),
    ("Binary to Decimal Converter", "easy",
     "Convert binary strings to decimal integers.", """
     def from_binary(bits):
         value = 0
         for b in bits:
             value = value * 2 + int(b)
         return value

     for bits in ["101", "1111", "100000", "1011011"]:
         print(f"{bits} -> {from_binary(bits)}")
     """),
    ("Decimal to Any Base", "medium",
     "Convert a decimal integer to any base from 2 to 16.", """
     DIGITS = "0123456789ABCDEF"

     def to_base(n, base):
         if n == 0:
             return "0"
         out = ""
         while n:
             out = DIGITS[n % base] + out
             n //= base
         return out

     for n, base in [(255, 16), (255, 8), (100, 2), (12345, 12)]:
         print(f"{n} in base {base}: {to_base(n, base)}")
     """),
    ("Roman Numeral Encoder", "medium",
     "Convert integers to Roman numerals.", """
     PAIRS = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
              (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
              (5, "V"), (4, "IV"), (1, "I")]

     def to_roman(n):
         out = ""
         for value, sym in PAIRS:
             while n >= value:
                 out += sym
                 n -= value
         return out

     for n in [4, 9, 14, 1990, 2026]:
         print(f"{n} -> {to_roman(n)}")
     """),
    ("Roman Numeral Decoder", "medium",
     "Convert Roman numerals back to integers.", """
     VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

     def from_roman(s):
         total = 0
         for i, ch in enumerate(s):
             v = VALUES[ch]
             if i + 1 < len(s) and VALUES[s[i + 1]] > v:
                 total -= v
             else:
                 total += v
         return total

     for s in ["IV", "IX", "XIV", "MCMXC", "MMXXVI"]:
         print(f"{s} -> {from_roman(s)}")
     """),
    ("Happy Value Checker", "medium",
     "Check the happy-value property by repeatedly squaring digits.", """
     def is_happy(n):
         seen = set()
         while n != 1 and n not in seen:
             seen.add(n)
             total = 0
             while n:
                 d = n % 10
                 total += d * d
                 n //= 10
             n = total
         return n == 1

     for n in [19, 2, 7, 20]:
         print(f"{n}: happy = {is_happy(n)}")
     """),
    ("Collatz Step Counter", "easy",
     "Count the steps for a value to reach 1 under the Collatz rule.", """
     def collatz_steps(n):
         steps = 0
         while n != 1:
             n = n // 2 if n % 2 == 0 else 3 * n + 1
             steps += 1
         return steps

     for n in [6, 27, 97, 1]:
         print(f"{n}: {collatz_steps(n)} steps")
     """),
    ("Perfect Square Checker", "easy",
     "Check whether an integer is a perfect square without floats.", """
     import math

     def is_square(n):
         if n < 0:
             return False
         r = math.isqrt(n)
         return r * r == n

     for n in [16, 20, 144, 1000000, 99]:
         print(f"{n}: square = {is_square(n)}")
     """),
    ("Factor Lister", "easy",
     "List all positive divisors of an integer.", """
     def factors(n):
         out = []
         for d in range(1, n + 1):
             if n % d == 0:
                 out.append(d)
         return out

     for n in [12, 28, 97]:
         print(f"{n}: {factors(n)}")
     """),
    ("GCD (Recursive Euclid)", "easy",
     "Compute the greatest common divisor with recursive Euclid.", """
     def gcd(a, b):
         return a if b == 0 else gcd(b, a % b)

     for a, b in [(48, 18), (270, 192), (17, 5)]:
         print(f"gcd({a}, {b}) = {gcd(a, b)}")
     """),
]
for title, diff, desc, code in NUM:
    S(title, "math", diff, desc, code)

# ---------------------------------------------------------------------------
# 5. Statistics (category: math)
# ---------------------------------------------------------------------------
STATS = [
    ("Mean Calculator", "easy",
     "Compute the arithmetic mean of a list with a manual loop.", """
     def mean(values):
         total = 0.0
         for v in values:
             total += v
         return total / len(values)

     data = [23, 41, 37, 29, 52, 44]
     print(f"data: {data}")
     print(f"mean: {mean(data):.2f}")
     """),
    ("Mode Finder with Counter", "easy",
     "Find the most common value in a list using collections.Counter.", """
     from collections import Counter

     data = [4, 1, 2, 2, 3, 4, 2, 5, 4, 2]
     counts = Counter(data)
     value, freq = counts.most_common(1)[0]
     print(f"data: {data}")
     print(f"mode: {value} (appears {freq} times)")
     """),
    ("Variance and Standard Deviation", "medium",
     "Compute population variance and standard deviation manually.", """
     import math

     def variance(values):
         total = 0.0
         for v in values:
             total += v
         m = total / len(values)
         sq = 0.0
         for v in values:
             sq += (v - m) ** 2
         return sq / len(values)

     data = [2, 4, 4, 4, 5, 5, 7, 9]
     var = variance(data)
     print(f"variance: {var:.2f}")
     print(f"std dev: {math.sqrt(var):.2f}")
     """),
    ("Weighted Average Calculator", "easy",
     "Compute a weighted average of grades.", """
     grades = [(92, 0.3), (85, 0.3), (78, 0.4)]
     total, weight_total = 0.0, 0.0
     for score, weight in grades:
         total += score * weight
         weight_total += weight
     print(f"weighted average: {total / weight_total:.2f}")
     """),
    ("Z-Score Calculator", "medium",
     "Compute z-scores for values given a mean and standard deviation.", """
     def z_score(x, mu, sigma):
         return (x - mu) / sigma

     mu, sigma = 100, 15
     for x in [85, 100, 130, 145]:
         print(f"x={x}: z = {z_score(x, mu, sigma):+.2f}")
     """),
    ("Min-Max Normalization", "medium",
     "Rescale values into the 0..1 range.", """
     def normalize(values):
         lo, hi = min(values), max(values)
         return [(v - lo) / (hi - lo) for v in values]

     data = [12, 20, 28, 36, 44]
     for raw, norm in zip(data, normalize(data)):
         print(f"{raw} -> {norm:.2f}")
     """),
    ("Data Range and Midrange", "easy",
     "Compute the range and midrange of a data set.", """
     data = [7, 13, 2, 20, 11, 5]
     lo, hi = min(data), max(data)
     print(f"data: {data}")
     print(f"range: {hi - lo}")
     print(f"midrange: {(lo + hi) / 2}")
     """),
    ("Coefficient of Variation", "medium",
     "Compute the ratio of standard deviation to mean as a percent.", """
     import math

     def cv(values):
         total = 0.0
         for v in values:
             total += v
         m = total / len(values)
         sq = 0.0
         for v in values:
             sq += (v - m) ** 2
         return math.sqrt(sq / len(values)) / m * 100

     for data in [[10, 12, 11, 13], [5, 50, 20, 80]]:
         print(f"{data}: CV = {cv(data):.1f}%")
     """),
]
for title, diff, desc, code in STATS:
    S(title, "math", diff, desc, code)

# ---------------------------------------------------------------------------
# 6. String utilities (category: strings)
# ---------------------------------------------------------------------------
STR = [
    ("Vowel Counter", "easy",
     "Count the vowels in a string with a simple loop.", """
     def count_vowels(text):
         count = 0
         for ch in text.lower():
             if ch in "aeiou":
                 count += 1
         return count

     for s in ["hello world", "Python", "rhythm", "education"]:
         print(f"{s!r}: {count_vowels(s)} vowels")
     """),
    ("Vowel Counter (comprehension)", "easy",
     "Count vowels using a generator expression inside len via list.", """
     def count_vowels(text):
         return len([ch for ch in text.lower() if ch in "aeiou"])

     for s in ["hello world", "Python", "rhythm", "education"]:
         print(f"{s!r}: {count_vowels(s)} vowels")
     """),
    ("Consonant Counter", "easy",
     "Count alphabetic characters that are not vowels.", """
     def count_consonants(text):
         count = 0
         for ch in text.lower():
             if ch.isalpha() and ch not in "aeiou":
                 count += 1
         return count

     for s in ["hello world", "strengths", "aeiou"]:
         print(f"{s!r}: {count_consonants(s)} consonants")
     """),
    ("Capitalize Every Word", "easy",
     "Capitalize the first letter of each word without str.title edge cases.", """
     def cap_words(text):
         return " ".join(w[:1].upper() + w[1:] for w in text.split())

     for s in ["hello world", "the quick brown fox", "python 3.10 rocks"]:
         print(cap_words(s))
     """),
    ("Swap Letter Case", "easy",
     "Swap uppercase and lowercase letters in a string.", """
     def swap(text):
         return "".join(c.lower() if c.isupper() else c.upper() for c in text)

     for s in ["Hello World", "PYTHON", "mIxEd CaSe"]:
         print(f"{s} -> {swap(s)}")
     """),
    ("Punctuation Remover", "easy",
     "Strip punctuation characters from text using str.translate.", """
     import string

     def clean(text):
         return text.translate(str.maketrans("", "", string.punctuation))

     for s in ["Hello, world!", "It's a te-st...", "no punct here"]:
         print(f"{s!r} -> {clean(s)!r}")
     """),
    ("Whitespace Collapser", "easy",
     "Collapse runs of whitespace into single spaces.", """
     def collapse(text):
         return " ".join(text.split())

     samples = ["  hello   world  ", "tabs\\tand\\nnewlines", "one two"]
     for s in samples:
         print(f"{s!r} -> {collapse(s)!r}")
     """),
    ("Snake Case to Camel Case", "easy",
     "Convert snake_case identifiers to camelCase.", """
     def to_camel(name):
         head, *rest = name.split("_")
         return head + "".join(w.capitalize() for w in rest)

     for name in ["user_name", "http_response_code", "already"]:
         print(f"{name} -> {to_camel(name)}")
     """),
    ("Camel Case to Snake Case", "medium",
     "Convert camelCase identifiers to snake_case with a loop.", """
     def to_snake(name):
         out = ""
         for ch in name:
             if ch.isupper():
                 out += "_" + ch.lower()
             else:
                 out += ch
         return out

     for name in ["userName", "httpResponseCode", "simple"]:
         print(f"{name} -> {to_snake(name)}")
     """),
    ("Kebab Case Converter", "easy",
     "Convert phrases to kebab-case slugs.", """
     def kebab(text):
         return "-".join(text.lower().split())

     for s in ["Hello World", "My First Blog Post", "Python Tips"]:
         print(f"{s!r} -> {kebab(s)!r}")
     """),
    ("Acronym Builder", "easy",
     "Build an acronym from the first letter of each word.", """
     def acronym(phrase):
         return "".join(w[0].upper() for w in phrase.split())

     for s in ["frequently asked questions",
               "random access memory", "keep it simple"]:
         print(f"{s} -> {acronym(s)}")
     """),
    ("Initials Extractor", "easy",
     "Extract initials from full names.", """
     def initials(name):
         return ". ".join(part[0].upper() for part in name.split()) + "."

     for name in ["ada lovelace", "grace brewster hopper", "alan turing"]:
         print(f"{name} -> {initials(name)}")
     """),
    ("Longest Word Finder", "easy",
     "Find the longest word in a passage.", """
     text = "the quick brown fox jumped over the extraordinarily lazy dog"
     longest = ""
     for word in text.split():
         if len(word) > len(longest):
             longest = word
     print(f"longest word: {longest} ({len(longest)} letters)")
     """),
    ("Average Word Length", "easy",
     "Compute the average word length in a text.", """
     text = "readability counts and simple is better than complex"
     words = text.split()
     total = 0
     for w in words:
         total += len(w)
     print(f"{len(words)} words, average length {total / len(words):.2f}")
     """),
    ("String Truncator", "easy",
     "Truncate long strings and append an ellipsis.", """
     def truncate(text, width):
         return text if len(text) <= width else text[:width - 3] + "..."

     for s in ["short", "this is a much longer line of text"]:
         print(truncate(s, 20))
     """),
    ("Word Wrap with textwrap", "easy",
     "Wrap a long line to a fixed width using textwrap.", """
     import textwrap

     text = ("Python's textwrap module makes it easy to wrap long strings "
             "into neat fixed-width lines for terminal output.")
     for line in textwrap.wrap(text, width=30):
         print(line)
     """),
    ("Text Banner Maker", "easy",
     "Center a title inside a decorated banner.", """
     def banner(text, width=30, fill="*"):
         print(fill * width)
         print(text.center(width))
         print(fill * width)

     banner("CodeRunner")
     banner("v2.0", width=20, fill="=")
     """),
    ("Count Occurrences in Text", "easy",
     "Count how many times a word appears in a passage.", """
     text = "to be or not to be that is the question to ponder"
     for target in ["to", "be", "question"]:
         print(f"{target!r}: {text.split().count(target)}")
     """),
    ("Find All Character Positions", "easy",
     "List every index where a character appears in a string.", """
     def positions(text, ch):
         return [i for i, c in enumerate(text) if c == ch]

     s = "mississippi"
     for ch in "sip":
         print(f"{ch!r} in {s!r}: {positions(s, ch)}")
     """),
    ("Remove Duplicate Characters", "easy",
     "Remove repeated characters while keeping first-seen order.", """
     def dedupe(text):
         seen = []
         for ch in text:
             if ch not in seen:
                 seen.append(ch)
         return "".join(seen)

     for s in ["programming", "aabbccdd", "hello world"]:
         print(f"{s} -> {dedupe(s)}")
     """),
    ("Remove Duplicates with dict.fromkeys", "easy",
     "One-liner duplicate removal that preserves order via dict keys.", """
     for s in ["programming", "aabbccdd", "hello world"]:
         print(f"{s} -> {''.join(dict.fromkeys(s))}")
     """),
    ("Anagram Checker", "easy",
     "Check whether two words use exactly the same letters via Counter.", """
     from collections import Counter

     def is_anagram(a, b):
         return Counter(a.lower()) == Counter(b.lower())

     pairs = [("listen", "silent"), ("hello", "world"), ("Dormitory", "dirtyroom")]
     for a, b in pairs:
         print(f"{a} / {b}: {is_anagram(a, b)}")
     """),
    ("Anagram Checker (letter tally)", "easy",
     "Check anagrams with a hand-built letter tally dictionary.", """
     def tally(word):
         counts = {}
         for ch in word.lower():
             counts[ch] = counts.get(ch, 0) + 1
         return counts

     pairs = [("listen", "silent"), ("hello", "world")]
     for a, b in pairs:
         print(f"{a} / {b}: {tally(a) == tally(b)}")
     """),
    ("Pangram Checker", "easy",
     "Check whether a phrase uses every letter of the alphabet.", """
     import string

     def is_pangram(text):
         letters = set(text.lower())
         return all(ch in letters for ch in string.ascii_lowercase)

     for s in ["The quick brown fox jumps over the lazy dog", "Hello world"]:
         print(f"{s!r}: {is_pangram(s)}")
     """),
    ("Pig Latin Translator", "medium",
     "Translate English words into pig latin.", """
     def pig_latin(word):
         if word[0] in "aeiou":
             return word + "way"
         for i, ch in enumerate(word):
             if ch in "aeiou":
                 return word[i:] + word[:i] + "ay"
         return word + "ay"

     for w in ["python", "apple", "string", "egg"]:
         print(f"{w} -> {pig_latin(w)}")
     """),
    ("Leetspeak Converter", "easy",
     "Replace letters with classic leetspeak digits.", """
     TABLE = str.maketrans("aeiost", "431057")

     for s in ["leet speak is old school", "python master"]:
         print(s.translate(TABLE))
     """),
    ("Morse Code Encoder", "medium",
     "Encode text as Morse code dots and dashes.", """
     MORSE = {"a": ".-", "b": "-...", "c": "-.-.", "d": "-..", "e": ".",
              "f": "..-.", "g": "--.", "h": "....", "i": "..", "j": ".---",
              "k": "-.-", "l": ".-..", "m": "--", "n": "-.", "o": "---",
              "p": ".--.", "q": "--.-", "r": ".-.", "s": "...", "t": "-",
              "u": "..-", "v": "...-", "w": ".--", "x": "-..-", "y": "-.--",
              "z": "--.."}

     def encode(text):
         return " ".join(MORSE[c] for c in text.lower() if c in MORSE)

     for s in ["sos", "hello", "python"]:
         print(f"{s} -> {encode(s)}")
     """),
    ("Morse Code Decoder", "medium",
     "Decode Morse code back into letters.", """
     MORSE = {"a": ".-", "b": "-...", "c": "-.-.", "d": "-..", "e": ".",
              "h": "....", "l": ".-..", "n": "-.", "o": "---", "p": ".--.",
              "s": "...", "t": "-", "y": "-.--"}
     REVERSE = {v: k for k, v in MORSE.items()}

     def decode(code):
         return "".join(REVERSE.get(sym, "?") for sym in code.split())

     for code in ["... --- ...", ".... . .-.. .-.. ---", ".--. -.-- - .... --- -."]:
         print(f"{code} -> {decode(code)}")
     """),
    ("Run-Length Encoder", "medium",
     "Compress repeated characters into count+character pairs.", """
     def rle(text):
         out, i = "", 0
         while i < len(text):
             j = i
             while j < len(text) and text[j] == text[i]:
                 j += 1
             out += f"{j - i}{text[i]}"
             i = j
         return out

     for s in ["aaabbbcccd", "wwwwaaadexxxxxx", "abc"]:
         print(f"{s} -> {rle(s)}")
     """),
    ("Run-Length Decoder", "medium",
     "Expand count+character pairs back into the original string.", """
     import re

     def unrle(encoded):
         out = ""
         for count, ch in re.findall(r"(\\d+)(\\D)", encoded):
             out += ch * int(count)
         return out

     for s in ["3a3b3c1d", "4w3a1d1e6x"]:
         print(f"{s} -> {unrle(s)}")
     """),
    ("Reverse Word Order", "easy",
     "Reverse the order of words in a phrase, keeping each word intact.", """
     def reverse_words(text):
         return " ".join(text.split()[::-1])

     for s in ["hello world again", "keep calm and code on"]:
         print(f"{s!r} -> {reverse_words(s)!r}")
     """),
    ("Alternating Caps Effect", "easy",
     "Alternate upper and lower case across the letters of a string.", """
     def alternate(text):
         out, upper = "", True
         for ch in text:
             if ch.isalpha():
                 out += ch.upper() if upper else ch.lower()
                 upper = not upper
             else:
                 out += ch
         return out

     for s in ["hello world", "python"]:
         print(alternate(s))
     """),
    ("Character Frequency Table", "easy",
     "Tally character frequencies with a plain dictionary.", """
     text = "abracadabra"
     freq = {}
     for ch in text:
         freq[ch] = freq.get(ch, 0) + 1
     for ch, n in freq.items():
         print(f"{ch}: {n}")
     """),
    ("String to Character Codes", "easy",
     "Show the ord code point for each character.", """
     for ch in "Hi! 42":
         print(f"{ch!r} -> {ord(ch)}")
     """),
    ("String Padding Toolkit", "easy",
     "Pad strings with zfill, ljust, and rjust.", """
     n = "42"
     print(n.zfill(6))
     print("left".ljust(10, ".") + "|")
     print("right".rjust(10, ".") + "|")
     print("mid".center(11, "-"))
     """),
    ("Strip Leading and Ending Spaces", "easy",
     "Demonstrate strip, lstrip, and rstrip on messy input.", """
     s = "   padded value   "
     print(f"strip  -> {s.strip()!r}")
     print(f"lstrip -> {s.lstrip()!r}")
     print(f"rstrip -> {s.rstrip()!r}")
     print(f"custom -> {'xxdataxx'.strip('x')!r}")
     """),
    ("Startswith and Endswith Demo", "easy",
     "Filter filenames by prefix and suffix checks.", """
     files = ["report.pdf", "draft_report.docx", "image.png", "report_final.pdf"]
     for f in files:
         if f.startswith("report") and f.endswith(".pdf"):
             print(f"match: {f}")
         else:
             print(f"skip:  {f}")
     """),
    ("Partition and Split Demo", "easy",
     "Compare str.partition with str.split for key=value strings.", """
     entry = "timeout=30=seconds"
     print(entry.partition("="))
     print(entry.split("="))
     print(entry.rpartition("="))
     """),
    ("Casefold Comparison Demo", "easy",
     "Compare strings case-insensitively with casefold.", """
     pairs = [("STRASSE", "strasse"), ("Hello", "hello"), ("abc", "abd")]
     for a, b in pairs:
         print(f"{a} vs {b}: {a.casefold() == b.casefold()}")
     """),
]
for title, diff, desc, code in STR:
    S(title, "strings", diff, desc, code)

# ---------------------------------------------------------------------------
# 7. Regex recipes (category: regex)
# ---------------------------------------------------------------------------
RGX = [
    ("Extract Email Addresses", "medium",
     "Pull email addresses out of free text with a regex.", """
     import re

     text = "Contact alex.rivera@meridiansystems.com or support@lakeport.io today."
     for addr in re.findall(r"[\\w.+-]+@[\\w-]+\\.[\\w.]+", text):
         print(addr)
     """),
    ("Extract ISO Dates", "easy",
     "Find all YYYY-MM-DD dates in a block of text.", """
     import re

     text = "Released 2024-11-05, patched 2025-01-20, EOL 2026-07-01."
     print(re.findall(r"\\d{4}-\\d{2}-\\d{2}", text))
     """),
    ("Extract Numeric Tokens", "easy",
     "Extract integers and decimals from a string.", """
     import re

     text = "Order 42 shipped: 3 items, total 59.90 dollars, weight 1.25 kg"
     print(re.findall(r"\\d+(?:\\.\\d+)?", text))
     """),
    ("Find Capitalized Words", "easy",
     "Find words that start with a capital letter.", """
     import re

     text = "Alice met Bob near the Old Mill on Tuesday."
     print(re.findall(r"\\b[A-Z][a-z]+\\b", text))
     """),
    ("Split on Multiple Delimiters", "easy",
     "Split a string on commas, semicolons, or pipes at once.", """
     import re

     line = "red,green;blue|yellow, purple"
     print(re.split(r"\\s*[,;|]\\s*", line))
     """),
    ("Censor Words with re.sub", "easy",
     "Replace listed words with asterisks using alternation.", """
     import re

     text = "this darn code is a real pain to debug"
     print(re.sub(r"\\b(darn|pain)\\b", "****", text))
     """),
    ("Named Groups for Name Parsing", "medium",
     "Parse 'Last, First' strings using named capture groups.", """
     import re

     pattern = re.compile(r"(?P<last>[A-Za-z]+),\\s*(?P<first>[A-Za-z]+)")
     for s in ["Rivera, Alex", "Chen, Marcus", "Kim, Natalie"]:
         m = pattern.match(s)
         print(f"{m.group('first')} {m.group('last')}")
     """),
    ("Greedy vs Lazy Quantifiers", "medium",
     "Show the difference between .* and .*? on tagged text.", """
     import re

     s = "<b>bold</b> and <i>italic</i>"
     print(re.findall(r"<.*>", s))
     print(re.findall(r"<.*?>", s))
     """),
    ("Word Boundary Demo", "easy",
     "Show how word boundaries change what a pattern matches.", """
     import re

     text = "cat catalog concatenate cat."
     print(re.findall(r"cat", text))
     print(re.findall(r"\\bcat\\b", text))
     """),
    ("Validate Hex Colors", "easy",
     "Validate #RGB and #RRGGBB hex color strings.", """
     import re

     pattern = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
     for s in ["#fff", "#1a2b3c", "#12345", "blue", "#ABCDEF"]:
         print(f"{s}: {bool(pattern.match(s))}")
     """),
    ("Validate 24-Hour Times", "easy",
     "Validate HH:MM strings on a 24-hour clock.", """
     import re

     pattern = re.compile(r"^(?:[01]\\d|2[0-3]):[0-5]\\d$")
     for s in ["09:30", "23:59", "24:00", "7:15", "12:60"]:
         print(f"{s}: {bool(pattern.match(s))}")
     """),
    ("Extract At-Mentions", "easy",
     "Extract @username mentions from a message.", """
     import re

     msg = "thanks @alex_rivera and @natalie.kim for reviewing! cc @marcus"
     print(re.findall(r"@([\\w.]+)", msg))
     """),
    ("Normalize Phone Digits", "medium",
     "Strip formatting from phone strings and group the digits.", """
     import re

     def normalize(phone):
         digits = re.sub(r"\\D", "", phone)
         return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"

     for p in ["555-867-5309", "(555) 123 4567", "555.246.8100"]:
         print(f"{p} -> {normalize(p)}")
     """),
    ("Lookahead Assertion Demo", "hard",
     "Match values only when followed by a unit using lookahead.", """
     import re

     text = "10kg 25mi 40kg 7s"
     print(re.findall(r"\\d+(?=kg)", text))
     print(re.findall(r"\\d+(?=mi)", text))
     """),
    ("Lookbehind Assertion Demo", "hard",
     "Extract amounts only when preceded by a currency sign.", """
     import re

     text = "items: $40, 25 units, $7.50, 99 points"
     print(re.findall(r"(?<=\\$)\\d+(?:\\.\\d+)?", text))
     """),
    ("Find Doubled Words", "medium",
     "Detect accidentally repeated words with a backreference.", """
     import re

     text = "this this sentence has has some doubled words words"
     for m in re.finditer(r"\\b(\\w+)\\s+\\1\\b", text):
         print(f"doubled: {m.group(1)} at {m.start()}")
     """),
    ("Verbose Regex Pattern", "medium",
     "Write a readable regex using re.VERBOSE with comments.", """
     import re

     pattern = re.compile(r\"\"\"
         (?P<area>\\d{3})   # area code
         [-\\s]?
         (?P<mid>\\d{3})    # first three
         [-\\s]?
         (?P<tail>\\d{4})   # last four
     \"\"\", re.VERBOSE)
     m = pattern.search("call 555 867 5309 now")
     print(m.group("area"), m.group("mid"), m.group("tail"))
     """),
    ("re.subn Replacement Counter", "easy",
     "Count how many substitutions re.subn performed.", """
     import re

     text = "one fish two fish red fish blue fish"
     new, count = re.subn(r"fish", "cat", text)
     print(new)
     print(f"replacements: {count}")
     """),
    ("Anchors and Multiline Flag", "medium",
     "Use ^ and $ anchors with re.MULTILINE on multi-line text.", """
     import re

     log = "OK step one\\nFAIL step two\\nOK step three"
     print(re.findall(r"^OK .*$", log, re.MULTILINE))
     """),
    ("Character Class Cookbook", "easy",
     "Common character classes applied to one messy string.", """
     import re

     s = "User42 logged_in at 09:15! (id=7)"
     print("digits:", re.findall(r"\\d+", s))
     print("words: ", re.findall(r"[a-zA-Z]+", s))
     print("punct: ", re.findall(r"[^\\w\\s]", s))
     """),
]
for title, diff, desc, code in RGX:
    S(title, "regex", diff, desc, code)

# ---------------------------------------------------------------------------
# 8. Validators (category: strings)
# ---------------------------------------------------------------------------
VAL = [
    ("Email Validator", "easy",
     "Validate basic email address structure.", """
     import re

     def valid_email(s):
         return bool(re.match(r"^[\\w.+-]+@[\\w-]+\\.[\\w.]+$", s))

     for s in ["a@b.co", "no-at-sign", "user.name@site.org", "x@y"]:
         print(f"{s}: {valid_email(s)}")
     """),
    ("IPv4 Address Validator", "medium",
     "Validate dotted-quad IPv4 addresses without regex.", """
     def valid_ipv4(s):
         parts = s.split(".")
         if len(parts) != 4:
             return False
         for p in parts:
             if not p.isdigit() or not 0 <= int(p) <= 255 or (p != "0" and p.startswith("0")):
                 return False
         return True

     for s in ["192.168.1.1", "256.1.1.1", "10.0.0", "8.8.8.8", "01.2.3.4"]:
         print(f"{s}: {valid_ipv4(s)}")
     """),
    ("Password Strength Checker", "medium",
     "Score a password on length, case mix, digits, and symbols.", """
     def strength(pw):
         score = 0
         if len(pw) >= 8:
             score += 1
         if any(c.islower() for c in pw) and any(c.isupper() for c in pw):
             score += 1
         if any(c.isdigit() for c in pw):
             score += 1
         if any(not c.isalnum() for c in pw):
             score += 1
         return ["weak", "weak", "fair", "good", "strong"][score]

     for pw in ["abc", "abcdefgh", "Abcdef12", "Abcdef12!"]:
         print(f"{pw!r}: {strength(pw)}")
     """),
    ("Username Validator", "easy",
     "Validate usernames: 3-16 chars, letters, digits, underscore.", """
     import re

     def valid(name):
         return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9_]{2,15}$", name))

     for name in ["alex_rivera", "ab", "9lives", "good_name42", "way_too_long_username_here"]:
         print(f"{name}: {valid(name)}")
     """),
    ("ZIP Code Validator", "easy",
     "Validate US 5-digit and ZIP+4 codes.", """
     import re

     pattern = re.compile(r"^\\d{5}(?:-\\d{4})?$")
     for s in ["04901", "04901-1234", "1234", "abcde", "99999-12"]:
         print(f"{s}: {bool(pattern.match(s))}")
     """),
    ("Credit Card Luhn Check", "hard",
     "Validate card digits with the Luhn check-digit method.", """
     def luhn_ok(number):
         digits = [int(d) for d in str(number)][::-1]
         total = 0
         for i, d in enumerate(digits):
             if i % 2 == 1:
                 d *= 2
                 if d > 9:
                     d -= 9
             total += d
         return total % 10 == 0

     for n in ["4539578763621486", "1234567812345678", "79927398713"]:
         print(f"{n}: {luhn_ok(n)}")
     """),
    ("ISBN-10 Validator", "medium",
     "Validate ISBN-10 strings including the X check digit.", """
     def valid_isbn10(isbn):
         s = isbn.replace("-", "")
         if len(s) != 10:
             return False
         total = 0
         for i, ch in enumerate(s):
             if ch == "X" and i == 9:
                 v = 10
             elif ch.isdigit():
                 v = int(ch)
             else:
                 return False
             total += (10 - i) * v
         return total % 11 == 0

     for isbn in ["0-306-40615-2", "0306406152", "0-306-40615-3", "155860832X"]:
         print(f"{isbn}: {valid_isbn10(isbn)}")
     """),
    ("Semantic Version Validator", "easy",
     "Validate MAJOR.MINOR.PATCH version strings.", """
     import re

     pattern = re.compile(r"^\\d+\\.\\d+\\.\\d+$")
     for v in ["1.0.0", "2.10.3", "1.0", "v1.2.3", "3.4.5"]:
         print(f"{v}: {bool(pattern.match(v))}")
     """),
    ("Date String Validator", "easy",
     "Validate date strings by attempting to parse them.", """
     import datetime

     def valid_date(s):
         try:
             datetime.datetime.strptime(s, "%Y-%m-%d")
             return True
         except ValueError:
             return False

     for s in ["2026-07-20", "2026-02-30", "07/20/2026", "1999-12-31"]:
         print(f"{s}: {valid_date(s)}")
     """),
    ("URL Shape Validator", "easy",
     "Validate that a string looks like an http or https URL.", """
     import re

     pattern = re.compile(r"^https?://[\\w.-]+(?:/[\\w./%-]*)?$")
     for s in ["https://example.com", "http://a.b/c", "ftp://x.y", "not a url"]:
         print(f"{s}: {bool(pattern.match(s))}")
     """),
]
for title, diff, desc, code in VAL:
    S(title, "strings", diff, desc, code)

# ---------------------------------------------------------------------------
# 9. Date & time utilities (category: datetime) — all fixed dates, no now()
# ---------------------------------------------------------------------------
DT = [
    ("Days Between Two Dates", "easy",
     "Count the days separating two calendar dates.", """
     import datetime

     a = datetime.date(2026, 1, 1)
     b = datetime.date(2026, 7, 20)
     print(f"{a} -> {b}: {(b - a).days} days")
     print(f"{b} -> {a}: {(a - b).days} days")
     """),
    ("Weekday Name Finder", "easy",
     "Print the weekday name for a list of dates.", """
     import datetime

     for y, m, d in [(2026, 7, 20), (2000, 1, 1), (1969, 7, 20)]:
         day = datetime.date(y, m, d)
         print(f"{day}: {day.strftime('%A')}")
     """),
    ("Leap Year Checker", "easy",
     "Check leap years with the century rule.", """
     def is_leap(year):
         return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

     for y in [2024, 2026, 2000, 1900]:
         print(f"{y}: leap = {is_leap(y)}")
     """),
    ("Leap Year Checker (calendar module)", "easy",
     "Check leap years using calendar.isleap.", """
     import calendar

     for y in [2024, 2026, 2000, 1900]:
         print(f"{y}: leap = {calendar.isleap(y)}")
     """),
    ("Age at a Given Date", "easy",
     "Compute someone's age in years on a reference date.", """
     import datetime

     def age_on(birth, ref):
         years = ref.year - birth.year
         if (ref.month, ref.day) < (birth.month, birth.day):
             years -= 1
         return years

     ref = datetime.date(2026, 7, 20)
     for b in [datetime.date(1990, 8, 1), datetime.date(2000, 7, 20), datetime.date(1969, 12, 31)]:
         print(f"born {b}: {age_on(b, ref)} years old on {ref}")
     """),
    ("Add Days to a Date", "easy",
     "Shift a date forward and backward with timedelta.", """
     import datetime

     start = datetime.date(2026, 7, 20)
     for delta in [1, 30, -90, 365]:
         print(f"{start} {delta:+d} days = {start + datetime.timedelta(days=delta)}")
     """),
    ("Business Days Counter", "medium",
     "Count weekdays between two dates, skipping weekends.", """
     import datetime

     def business_days(a, b):
         count = 0
         d = a
         while d < b:
             if d.weekday() < 5:
                 count += 1
             d += datetime.timedelta(days=1)
         return count

     a = datetime.date(2026, 7, 1)
     b = datetime.date(2026, 7, 20)
     print(f"{a} -> {b}: {business_days(a, b)} business days")
     """),
    ("ISO Week Finder", "easy",
     "Show ISO year, week, and weekday for a date.", """
     import datetime

     for y, m, d in [(2026, 1, 1), (2026, 7, 20), (2026, 12, 31)]:
         iso = datetime.date(y, m, d).isocalendar()
         print(f"{y}-{m:02d}-{d:02d}: year={iso[0]} week={iso[1]} day={iso[2]}")
     """),
    ("Last Day of the Month", "easy",
     "Find month length and final day using calendar.monthrange.", """
     import calendar

     for y, m in [(2026, 2), (2024, 2), (2026, 7), (2026, 12)]:
         _, days = calendar.monthrange(y, m)
         print(f"{y}-{m:02d}: {days} days, ends on day {days}")
     """),
    ("Quarter Finder", "easy",
     "Map dates to fiscal quarters.", """
     import datetime

     def quarter(d):
         return (d.month - 1) // 3 + 1

     for y, m, d in [(2026, 1, 15), (2026, 5, 1), (2026, 7, 20), (2026, 11, 30)]:
         day = datetime.date(y, m, d)
         print(f"{day}: Q{quarter(day)}")
     """),
    ("Date Formatting Showcase", "easy",
     "Format one date many ways with strftime.", """
     import datetime

     d = datetime.date(2026, 7, 20)
     for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%B %d, %Y", "%a %b %d", "%j"]:
         print(f"{fmt:12} -> {d.strftime(fmt)}")
     """),
    ("Parse Mixed Date Formats", "medium",
     "Try several strptime formats until one works.", """
     import datetime

     FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%B %d, %Y"]

     def parse(s):
         for fmt in FORMATS:
             try:
                 return datetime.datetime.strptime(s, fmt).date()
             except ValueError:
                 continue
         return None

     for s in ["2026-07-20", "20/07/2026", "July 20, 2026", "garbage"]:
         print(f"{s!r} -> {parse(s)}")
     """),
    ("Timedelta Breakdown", "easy",
     "Break a duration into days, hours, and minutes.", """
     import datetime

     delta = datetime.timedelta(days=2, hours=5, minutes=42)
     total_minutes = delta.days * 24 * 60 + delta.seconds // 60
     print(f"total minutes: {total_minutes}")
     print(f"days={delta.days}, hours={delta.seconds // 3600}, minutes={delta.seconds % 3600 // 60}")
     """),
    ("Seconds to HH:MM:SS", "easy",
     "Format a duration in seconds as a clock string.", """
     def hms(seconds):
         h, rem = divmod(seconds, 3600)
         m, s = divmod(rem, 60)
         return f"{h:02d}:{m:02d}:{s:02d}"

     for sec in [59, 3600, 3725, 86399]:
         print(f"{sec:6d} -> {hms(sec)}")
     """),
    ("Day of Year Calculator", "easy",
     "Compute the ordinal day of the year for a date.", """
     import datetime

     for y, m, d in [(2026, 1, 1), (2026, 7, 20), (2026, 12, 31)]:
         day = datetime.date(y, m, d)
         print(f"{day}: day {day.timetuple().tm_yday} of the year")
     """),
    ("Next Friday Finder", "easy",
     "Find the next Friday after a fixed date.", """
     import datetime

     def next_friday(d):
         ahead = (4 - d.weekday()) % 7
         if ahead == 0:
             ahead = 7
         return d + datetime.timedelta(days=ahead)

     for y, m, d in [(2026, 7, 20), (2026, 7, 24), (2026, 7, 25)]:
         start = datetime.date(y, m, d)
         print(f"{start} -> {next_friday(start)}")
     """),
    ("Zodiac Sign by Birthday", "medium",
     "Look up the zodiac sign for a birth date.", """
     SIGNS = [(120, "Capricorn"), (218, "Aquarius"), (320, "Pisces"), (420, "Aries"),
              (521, "Taurus"), (621, "Gemini"), (722, "Cancer"), (823, "Leo"),
              (923, "Virgo"), (1023, "Libra"), (1122, "Scorpio"), (1222, "Sagittarius"),
              (1231, "Capricorn")]

     def zodiac(month, day):
         key = month * 100 + day
         for limit, sign in SIGNS:
             if key <= limit:
                 return sign

     for m, d in [(7, 20), (1, 1), (11, 30), (3, 21)]:
         print(f"{m:02d}/{d:02d}: {zodiac(m, d)}")
     """),
    ("Month Grid Printer", "easy",
     "Print a text calendar for one month.", """
     import calendar

     print(calendar.month(2026, 7))
     """),
]
for title, diff, desc, code in DT:
    S(title, "datetime", diff, desc, code)

# ---------------------------------------------------------------------------
# 10. Text analytics (category: strings)
# ---------------------------------------------------------------------------
TXT = [
    ("Reading Time Estimator", "easy",
     "Estimate reading time from word count at 200 wpm.", """
     import math

     text = ("Python is a high-level language known for readable syntax "
             "and batteries-included standard libraries. ") * 40
     words = len(text.split())
     print(f"{words} words")
     print(f"about {math.ceil(words / 200)} minute(s) to read")
     """),
    ("Sentence Counter", "easy",
     "Count sentences by terminal punctuation.", """
     import re

     text = "Hello there! How are you? I am fine. Great."
     parts = [p for p in re.split(r"[.!?]+", text) if p.strip()]
     print(f"sentences: {len(parts)}")
     for p in parts:
         print(f"- {p.strip()}")
     """),
    ("Unique Word Counter", "easy",
     "Count distinct words ignoring case and punctuation.", """
     import re

     text = "The cat and the dog. The DOG chased the cat!"
     words = re.findall(r"[a-z']+", text.lower())
     print(f"total words: {len(words)}")
     print(f"unique words: {len(set(words))}")
     """),
    ("Most Frequent Words", "easy",
     "Show the top three words in a passage with Counter.", """
     from collections import Counter

     text = "the rain in maine falls mainly on the plain the rain again"
     counts = Counter(text.split())
     for word, n in counts.most_common(3):
         print(f"{word}: {n}")
     """),
    ("Letter Frequency Bars", "medium",
     "Draw an ASCII bar chart of letter frequencies.", """
     text = "banana bandana cabana"
     counts = {}
     for ch in text:
         if ch.isalpha():
             counts[ch] = counts.get(ch, 0) + 1
     for ch in "abdn":
         print(f"{ch}: {'#' * counts.get(ch, 0)} ({counts.get(ch, 0)})")
     """),
    ("Word Length Distribution", "easy",
     "Tally how many words have each length.", """
     text = "a bb ccc bb a dddd ccc bb"
     dist = {}
     for w in text.split():
         dist[len(w)] = dist.get(len(w), 0) + 1
     for length in range(1, 5):
         print(f"length {length}: {dist.get(length, 0)} word(s)")
     """),
    ("Capitalization Statistics", "easy",
     "Count uppercase, lowercase, digit, and other characters.", """
     text = "Hello World 2026! CodeRunner FTW?"
     upper = lower = digit = other = 0
     for ch in text:
         if ch.isupper():
             upper += 1
         elif ch.islower():
             lower += 1
         elif ch.isdigit():
             digit += 1
         else:
             other += 1
     print(f"upper={upper} lower={lower} digit={digit} other={other}")
     """),
    ("Syllable Estimator", "medium",
     "Estimate syllables by counting vowel groups.", """
     import re

     def syllables(word):
         groups = re.findall(r"[aeiouy]+", word.lower())
         n = len(groups)
         if word.lower().endswith("e") and n > 1:
             n -= 1
         return max(n, 1)

     for w in ["python", "code", "beautiful", "queue", "strength"]:
         print(f"{w}: ~{syllables(w)} syllable(s)")
     """),
]
for title, diff, desc, code in TXT:
    S(title, "strings", diff, desc, code)

# ---------------------------------------------------------------------------
# 11. Encoding & unicode (category: strings)
# ---------------------------------------------------------------------------
ENC = [
    ("Base64 Encode and Decode", "easy",
     "Round-trip a string through base64.", """
     import base64

     msg = "CodeRunner rocks!"
     encoded = base64.b64encode(msg.encode()).decode()
     print(f"encoded: {encoded}")
     print(f"decoded: {base64.b64decode(encoded).decode()}")
     """),
    ("Text to Binary Bits", "easy",
     "Show each character of a string as 8 binary bits.", """
     for ch in "Hi!":
         print(f"{ch!r} -> {format(ord(ch), '08b')}")
     """),
    ("Unicode Name Lookup", "easy",
     "Print the official unicode name of characters.", """
     import unicodedata

     for ch in "A9@né":
         print(f"{ch!r}: {unicodedata.name(ch)}")
     """),
    ("Accent Stripper", "medium",
     "Remove accents by decomposing and dropping combining marks.", """
     import unicodedata

     def strip_accents(text):
         norm = unicodedata.normalize("NFD", text)
         return "".join(c for c in norm if not unicodedata.combining(c))

     for s in ["café", "naïve", "über", "crème"]:
         print(f"{s} -> {strip_accents(s)}")
     """),
    ("UTF-8 Byte Length Checker", "easy",
     "Compare character count with encoded byte length.", """
     for s in ["abc", "café", "日本語", "🐍"]:
         print(f"{s!r}: {len(s)} chars, {len(s.encode('utf-8'))} bytes")
     """),
    ("Hex Dump of a String", "medium",
     "Print a small hex dump of an encoded string.", """
     data = "CodeRunner".encode()
     for i in range(0, len(data), 4):
         chunk = data[i:i + 4]
         hexpart = " ".join(f"{b:02x}" for b in chunk)
         print(f"{i:04d}: {hexpart:<12} {chunk.decode()}")
     """),
]
for title, diff, desc, code in ENC:
    S(title, "strings", diff, desc, code)

# ---------------------------------------------------------------------------
# 12. Data structures (category: data-structures)
# ---------------------------------------------------------------------------
DS = [
    ("Queue with deque", "easy",
     "Use collections.deque as a FIFO queue.", """
     from collections import deque

     q = deque()
     for job in ["build", "test", "deploy"]:
         q.append(job)
         print(f"enqueued {job}")
     while q:
         print(f"processing {q.popleft()}")
     """),
    ("Circular Buffer Class", "medium",
     "A fixed-size ring buffer that overwrites the oldest entry.", """
     class RingBuffer:
         def __init__(self, size):
             self.size = size
             self.data = []

         def add(self, item):
             if len(self.data) == self.size:
                 self.data.pop(0)
             self.data.append(item)

     rb = RingBuffer(3)
     for i in [1, 2, 3, 4, 5]:
         rb.add(i)
         print(f"after add({i}): {rb.data}")
     """),
    ("Stack with Minimum Tracking", "medium",
     "A stack that reports its minimum element in O(1).", """
     class MinStack:
         def __init__(self):
             self.items = []
             self.mins = []

         def push(self, x):
             self.items.append(x)
             self.mins.append(x if not self.mins else min(x, self.mins[-1]))

         def pop(self):
             self.mins.pop()
             return self.items.pop()

         def minimum(self):
             return self.mins[-1]

     s = MinStack()
     for x in [5, 2, 7, 1]:
         s.push(x)
         print(f"pushed {x}, min = {s.minimum()}")
     s.pop()
     print(f"after pop, min = {s.minimum()}")
     """),
    ("Doubly Linked List", "hard",
     "A doubly linked list with append, prepend, and both-direction walks.", """
     class Node:
         def __init__(self, value):
             self.value = value
             self.prev = None
             self.next = None

     class DList:
         def __init__(self):
             self.head = None
             self.tail = None

         def append(self, value):
             node = Node(value)
             if not self.head:
                 self.head = self.tail = node
             else:
                 node.prev = self.tail
                 self.tail.next = node
                 self.tail = node

         def forward(self):
             out, n = [], self.head
             while n:
                 out.append(n.value)
                 n = n.next
             return out

         def backward(self):
             out, n = [], self.tail
             while n:
                 out.append(n.value)
                 n = n.prev
             return out

     d = DList()
     for v in [1, 2, 3, 4]:
         d.append(v)
     print(f"forward:  {d.forward()}")
     print(f"backward: {d.backward()}")
     """),
    ("Binary Tree Inorder Walk", "medium",
     "Build a small binary tree and walk it inorder.", """
     class Node:
         def __init__(self, value, left=None, right=None):
             self.value = value
             self.left = left
             self.right = right

     def inorder(node):
         if node is None:
             return []
         return inorder(node.left) + [node.value] + inorder(node.right)

     root = Node(4, Node(2, Node(1), Node(3)), Node(6, Node(5), Node(7)))
     print(f"inorder: {inorder(root)}")
     """),
    ("Binary Tree Height", "medium",
     "Compute the height of a binary tree recursively.", """
     class Node:
         def __init__(self, value, left=None, right=None):
             self.value = value
             self.left = left
             self.right = right

     def height(node):
         if node is None:
             return 0
         return 1 + max(height(node.left), height(node.right))

     root = Node(1, Node(2, Node(4, Node(8))), Node(3))
     print(f"height: {height(root)}")
     """),
    ("BST Insert and Lookup", "medium",
     "Insert values into a binary tree ordered by key and look them up.", """
     class Node:
         def __init__(self, value):
             self.value = value
             self.left = None
             self.right = None

     def insert(node, value):
         if node is None:
             return Node(value)
         if value < node.value:
             node.left = insert(node.left, value)
         else:
             node.right = insert(node.right, value)
         return node

     def contains(node, value):
         while node:
             if value == node.value:
                 return True
             node = node.left if value < node.value else node.right
         return False

     root = None
     for v in [50, 30, 70, 20, 40]:
         root = insert(root, v)
     for probe in [40, 45, 70]:
         print(f"contains({probe}) = {contains(root, probe)}")
     """),
    ("Balanced Brackets Checker", "medium",
     "Check bracket balance with a stack.", """
     PAIRS = {")": "(", "]": "[", "}": "{"}

     def balanced(s):
         stack = []
         for ch in s:
             if ch in "([{":
                 stack.append(ch)
             elif ch in PAIRS:
                 if not stack or stack.pop() != PAIRS[ch]:
                     return False
         return not stack

     for s in ["(a[b]{c})", "([)]", "((()))", "(]"]:
         print(f"{s}: {balanced(s)}")
     """),
    ("Postfix Expression Evaluator", "hard",
     "Evaluate reverse Polish notation with a stack.", """
     def rpn(tokens):
         stack = []
         for t in tokens.split():
             if t in "+-*/":
                 b, a = stack.pop(), stack.pop()
                 if t == "+":
                     stack.append(a + b)
                 elif t == "-":
                     stack.append(a - b)
                 elif t == "*":
                     stack.append(a * b)
                 else:
                     stack.append(a / b)
             else:
                 stack.append(float(t))
         return stack[0]

     for expr in ["3 4 +", "5 1 2 + 4 * + 3 -", "6 2 /"]:
         print(f"{expr} = {rpn(expr)}")
     """),
    ("Set Operations Walkthrough", "easy",
     "Union, intersection, and difference reported deterministically.", """
     a = [1, 2, 3, 4, 5]
     b = [4, 5, 6, 7]
     sa, sb = set(a), set(b)
     print(f"in both: {[x for x in a if x in sb]}")
     print(f"only in a: {[x for x in a if x not in sb]}")
     print(f"only in b: {[x for x in b if x not in sa]}")
     print(f"union size: {len(sa | sb)}")
     """),
    ("Dictionary Inverter", "easy",
     "Swap the keys and values of a dictionary.", """
     capitals = {"France": "Paris", "Japan": "Tokyo", "Kenya": "Nairobi"}
     by_city = {city: country for country, city in capitals.items()}
     for city, country in by_city.items():
         print(f"{city} is the capital of {country}")
     """),
    ("Nested Dictionary Flattener", "medium",
     "Flatten nested dictionaries into dotted keys.", """
     def flatten(d, prefix=""):
         out = {}
         for k, v in d.items():
             key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
             if isinstance(v, dict):
                 out.update(flatten(v, key))
             else:
                 out[key] = v
         return out

     config = {"server": {"host": "localhost", "port": 8080}, "debug": True}
     for k, v in flatten(config).items():
         print(f"{k} = {v}")
     """),
    ("Group Words by Length", "easy",
     "Group a word list into a dict keyed by word length.", """
     words = ["ant", "bee", "cheetah", "dog", "eagle", "fox", "giraffe"]
     groups = {}
     for w in words:
         groups.setdefault(len(w), []).append(w)
     for length, ws in groups.items():
         print(f"{length}: {ws}")
     """),
    ("Namedtuple Point Demo", "easy",
     "Use namedtuple for lightweight records.", """
     from collections import namedtuple

     Point = namedtuple("Point", ["x", "y"])
     p, q = Point(1, 2), Point(4, 6)
     print(f"p = {p}, q = {q}")
     print(f"dx={q.x - p.x}, dy={q.y - p.y}")
     print(f"as dict: {p._asdict()}")
     """),
    ("defaultdict Grouping Demo", "easy",
     "Group names by first letter with defaultdict.", """
     from collections import defaultdict

     names = ["ana", "ben", "amy", "bob", "cal", "art"]
     groups = defaultdict(list)
     for n in names:
         groups[n[0]].append(n)
     for letter in "abc":
         print(f"{letter}: {groups[letter]}")
     """),
    ("Vote Tally with Counter", "easy",
     "Tally votes and report the leaders in order.", """
     from collections import Counter

     votes = ["red", "blue", "red", "green", "blue", "red"]
     tally = Counter(votes)
     for color, n in tally.most_common():
         print(f"{color}: {n}")
     """),
    ("ChainMap Config Lookup", "medium",
     "Layer default, file, and CLI settings with ChainMap.", """
     from collections import ChainMap

     defaults = {"host": "localhost", "port": 80, "debug": False}
     file_cfg = {"port": 8080}
     cli_cfg = {"debug": True}
     cfg = ChainMap(cli_cfg, file_cfg, defaults)
     for key in ["host", "port", "debug"]:
         print(f"{key} = {cfg[key]}")
     """),
    ("Sliding Window Maximum", "hard",
     "Report the max of each fixed-size window using a deque.", """
     from collections import deque

     def window_max(values, k):
         dq, out = deque(), []
         for i, v in enumerate(values):
             while dq and values[dq[-1]] <= v:
                 dq.pop()
             dq.append(i)
             if dq[0] == i - k:
                 dq.popleft()
             if i >= k - 1:
                 out.append(values[dq[0]])
         return out

     data = [1, 3, -1, -3, 5, 3, 6, 7]
     print(f"data: {data}")
     print(f"window max (k=3): {window_max(data, 3)}")
     """),
    ("Memoized Power with lru_cache", "medium",
     "Cache repeated recursive power computations.", """
     from functools import lru_cache

     @lru_cache(maxsize=None)
     def power(base, exp):
         if exp == 0:
             return 1
         return base * power(base, exp - 1)

     for b, e in [(2, 10), (3, 5), (2, 10)]:
         print(f"{b}^{e} = {power(b, e)}")
     print(power.cache_info())
     """),
    ("Two-Stack Queue", "medium",
     "Implement a queue using two stacks.", """
     class Queue2:
         def __init__(self):
             self.inbox = []
             self.outbox = []

         def enqueue(self, x):
             self.inbox.append(x)

         def dequeue(self):
             if not self.outbox:
                 while self.inbox:
                     self.outbox.append(self.inbox.pop())
             return self.outbox.pop()

     q = Queue2()
     for x in [1, 2, 3]:
         q.enqueue(x)
     print(q.dequeue())
     q.enqueue(4)
     print(q.dequeue())
     print(q.dequeue())
     print(q.dequeue())
     """),
]
for title, diff, desc, code in DS:
    S(title, "data-structures", diff, desc, code)

# ---------------------------------------------------------------------------
# 13. Language basics & functional style (category: basics)
# ---------------------------------------------------------------------------
BAS = [
    ("map Function Demo", "easy",
     "Apply a function across a list with map.", """
     prices = [19.99, 4.50, 129.00]
     with_tax = list(map(lambda p: round(p * 1.08, 2), prices))
     print(f"before: {prices}")
     print(f"after:  {with_tax}")
     """),
    ("filter Function Demo", "easy",
     "Keep only matching items with filter.", """
     values = [12, -3, 0, 45, -7, 8]
     positives = list(filter(lambda v: v > 0, values))
     evens = list(filter(lambda v: v % 2 == 0, values))
     print(f"positives: {positives}")
     print(f"evens:     {evens}")
     """),
    ("Reduce to a Single Total", "easy",
     "Fold a list into one value with functools.reduce.", """
     from functools import reduce
     import operator

     nums = [3, 5, 2, 7]
     total = reduce(operator.add, nums)
     product = reduce(operator.mul, nums)
     print(f"total:   {total}")
     print(f"product: {product}")
     """),
    ("zip Two Lists Demo", "easy",
     "Pair names with scores using zip.", """
     names = ["ana", "ben", "cal"]
     scores = [88, 92, 79]
     for name, score in zip(names, scores):
         print(f"{name}: {score}")
     print(dict(zip(names, scores)))
     """),
    ("enumerate Demo", "easy",
     "Loop with automatic indexes via enumerate.", """
     tasks = ["write code", "run tests", "ship it"]
     for i, task in enumerate(tasks, start=1):
         print(f"{i}. {task}")
     """),
    ("Tuple Unpacking Tricks", "easy",
     "Swap, star-unpack, and nested unpacking in one snippet.", """
     a, b = 1, 2
     a, b = b, a
     print(f"swapped: a={a}, b={b}")
     first, *middle, last = [10, 20, 30, 40, 50]
     print(f"first={first}, middle={middle}, last={last}")
     (x, y), z = (3, 4), 5
     print(f"x={x}, y={y}, z={z}")
     """),
    ("Ternary Expression Demo", "easy",
     "Use conditional expressions for compact branching.", """
     for n in [-5, 0, 42]:
         label = "negative" if n < 0 else "zero" if n == 0 else "positive"
         print(f"{n}: {label}")
     """),
    ("F-String Formatting Tour", "easy",
     "Numbers, padding, dates, and the = debug specifier.", """
     import datetime

     value = 1234.5678
     print(f"{value:.2f}")
     print(f"{value:>12.1f}|")
     print(f"{value:,.0f}")
     ratio = 0.8756
     print(f"{ratio:.1%}")
     d = datetime.date(2026, 7, 20)
     print(f"{d:%B %d, %Y}")
     print(f"{value=}")
     """),
    ("Format Spec Alignment Demo", "easy",
     "Align columns with format specifications.", """
     rows = [("widget", 4, 19.99), ("gizmo", 12, 4.5), ("doohickey", 2, 129.0)]
     for name, qty, price in rows:
         print(f"{name:<10} {qty:>3} {price:>8.2f}")
     """),
    ("Walrus Operator Demo", "medium",
     "Assign inside expressions with the walrus operator.", """
     data = [3, 9, 1, 12, 7]
     if (biggest := max(data)) > 10:
         print(f"found a big one: {biggest}")
     while (chunk := data[:2]):
         print(f"chunk: {chunk}")
         data = data[2:]
     """),
    ("Lambda Mini Cookbook", "easy",
     "Small anonymous functions for keys and defaults.", """
     words = ["bb", "a", "ddd", "cc"]
     longest = max(words, key=lambda w: len(w))
     print(f"longest: {longest}")
     square = lambda x: x * x
     print([square(n) for n in range(1, 6)])
     """),
    ("any and all Demo", "easy",
     "Aggregate boolean checks over lists.", """
     grades = [72, 85, 91, 68]
     print(f"any failing (<70)? {any(g < 70 for g in grades)}")
     print(f"all passing (>=60)? {all(g >= 60 for g in grades)}")
     print(f"all above 90? {all(g > 90 for g in grades)}")
     """),
    ("Chained Comparison Demo", "easy",
     "Use chained comparisons for range checks.", """
     for temp in [-5, 15, 25, 40]:
         if 18 <= temp <= 26:
             print(f"{temp}C: comfortable")
         elif 0 <= temp < 18:
             print(f"{temp}C: chilly")
         else:
             print(f"{temp}C: extreme")
     """),
    ("List Slicing Tricks", "easy",
     "Copy, reverse, and stride through lists with slices.", """
     nums = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
     print(nums[::2])
     print(nums[1::2])
     print(nums[::-1])
     print(nums[3:7])
     print(nums[-3:])
     """),
    ("Dict Comprehension Demo", "easy",
     "Build dictionaries with comprehensions.", """
     words = ["apple", "banana", "cherry"]
     lengths = {w: len(w) for w in words}
     print(lengths)
     squares = {n: n * n for n in range(1, 6) if n % 2 == 1}
     print(squares)
     """),
    ("Nested List Comprehension", "medium",
     "Build a small multiplication grid with nested comprehensions.", """
     grid = [[r * c for c in range(1, 6)] for r in range(1, 4)]
     for row in grid:
         print(" ".join(f"{v:3d}" for v in row))
     """),
    ("Lazy Iteration with yield", "medium",
     "Stream values one at a time from a function with yield.", """
     def countdown(n):
         while n > 0:
             yield n
             n -= 1

     for v in countdown(5):
         print(f"t-minus {v}")
     print("liftoff!")
     """),
    ("Closure Counter Factory", "medium",
     "Create independent counters using closures.", """
     def make_counter():
         count = 0
         def bump():
             nonlocal count
             count += 1
             return count
         return bump

     a, b = make_counter(), make_counter()
     print(a(), a(), a())
     print(b())
     """),
    ("Basic Decorator Demo", "medium",
     "Wrap a function to log calls with a decorator.", """
     def announce(fn):
         def wrapper(*args):
             print(f"calling {fn.__name__}{args}")
             result = fn(*args)
             print(f"-> {result}")
             return result
         return wrapper

     @announce
     def add(a, b):
         return a + b

     add(2, 3)
     add(10, -4)
     """),
    ("Decorator with Arguments", "hard",
     "A decorator factory that repeats a function call.", """
     def repeat(times):
         def deco(fn):
             def wrapper(*args):
                 for _ in range(times):
                     fn(*args)
             return wrapper
         return deco

     @repeat(3)
     def greet(name):
         print(f"hello, {name}!")

     greet("world")
     """),
    ("args and kwargs Demo", "easy",
     "Accept flexible positional and keyword arguments.", """
     def report(*args, **kwargs):
         print(f"positional: {args}")
         for k, v in kwargs.items():
             print(f"  {k} = {v}")

     report(1, 2, 3, mode="fast", debug=True)
     report("solo")
     """),
    ("try except else finally", "easy",
     "Show all four clauses of exception handling.", """
     def divide(a, b):
         try:
             result = a / b
         except ZeroDivisionError:
             print(f"{a}/{b}: cannot divide by zero")
         else:
             print(f"{a}/{b} = {result}")
         finally:
             print("-- done --")

     divide(10, 2)
     divide(5, 0)
     """),
    ("Custom Exception Class", "medium",
     "Define and raise a domain-specific exception.", """
     class InsufficientFunds(Exception):
         def __init__(self, short):
             super().__init__(f"short by ${short:.2f}")
             self.short = short

     def withdraw(balance, amount):
         if amount > balance:
             raise InsufficientFunds(amount - balance)
         return balance - amount

     try:
         withdraw(50, 80)
     except InsufficientFunds as e:
         print(f"denied: {e}")
     print(f"ok: new balance {withdraw(100, 30)}")
     """),
    ("Global vs Local Scope", "easy",
     "Show how the global keyword changes assignment scope.", """
     counter = 0

     def bump_local():
         counter = 99
         return counter

     def bump_global():
         global counter
         counter += 1

     bump_local()
     print(f"after bump_local: {counter}")
     bump_global()
     bump_global()
     print(f"after bump_global x2: {counter}")
     """),
]
for title, diff, desc, code in BAS:
    S(title, "basics", diff, desc, code)

# ---------------------------------------------------------------------------
# 14. itertools toolbox (category: itertools)
# ---------------------------------------------------------------------------
ITR = [
    ("Permutations Demo", "easy",
     "List the orderings of a small set of letters.", """
     import itertools

     for p in itertools.permutations("abc"):
         print("".join(p))
     """),
    ("Combinations Demo", "easy",
     "Choose 2-element subsets from a list.", """
     import itertools

     team = ["ana", "ben", "cal", "dee"]
     for pair in itertools.combinations(team, 2):
         print(pair)
     """),
    ("Cartesian Product Demo", "easy",
     "Combine sizes and colors with itertools.product.", """
     import itertools

     for size, color in itertools.product(["S", "M"], ["red", "blue", "green"]):
         print(f"{size}-{color}")
     """),
    ("Cycle Through a Roster", "easy",
     "Repeat a roster of workers across a week of shifts with cycle.", """
     import itertools

     workers = itertools.cycle(["ana", "ben", "cal"])
     for day, worker in zip(["Mon", "Tue", "Wed", "Thu", "Fri"], workers):
         print(f"{day}: {worker}")
     """),
    ("Chain Lists Together", "easy",
     "Flatten several lists lazily with itertools.chain.", """
     import itertools

     a, b, c = [1, 2], [3, 4], [5]
     print(list(itertools.chain(a, b, c)))
     print(list(itertools.chain.from_iterable([a, b, c])))
     """),
    ("groupby Consecutive Runs", "medium",
     "Group consecutive equal items with itertools.groupby.", """
     import itertools

     s = "aaabbcaaa"
     for ch, run in itertools.groupby(s):
         print(f"{ch} x{len(list(run))}")
     """),
    ("Running Product with accumulate", "medium",
     "Produce running products using accumulate and operator.mul.", """
     import itertools
     import operator

     nums = [2, 3, 4, 5]
     print(list(itertools.accumulate(nums, operator.mul)))
     print(list(itertools.accumulate(nums, max)))
     """),
    ("compress Selector Demo", "easy",
     "Select items with a boolean mask via itertools.compress.", """
     import itertools

     items = ["a", "b", "c", "d", "e"]
     mask = [1, 0, 1, 0, 1]
     print(list(itertools.compress(items, mask)))
     """),
    ("takewhile and dropwhile", "medium",
     "Split a stream at the first failing condition.", """
     import itertools

     data = [1, 4, 6, 3, 8, 2]
     print(list(itertools.takewhile(lambda x: x < 6, data)))
     print(list(itertools.dropwhile(lambda x: x < 6, data)))
     """),
    ("zip_longest with Fill Value", "easy",
     "Zip uneven lists, padding the shorter one.", """
     import itertools

     a = [1, 2, 3]
     b = ["x", "y"]
     for pair in itertools.zip_longest(a, b, fillvalue="-"):
         print(pair)
     """),
    ("starmap Demo", "easy",
     "Apply a function to pre-bundled argument tuples.", """
     import itertools

     pairs = [(2, 5), (3, 2), (10, 3)]
     print(list(itertools.starmap(pow, pairs)))
     """),
]
for title, diff, desc, code in ITR:
    S(title, "itertools", diff, desc, code)

# ---------------------------------------------------------------------------
# 15. OOP patterns & class exercises (category: oop)
# ---------------------------------------------------------------------------
OOP = [
    ("Class Basics with Dog", "easy",
     "Define a class with attributes and methods.", """
     class Dog:
         def __init__(self, name, age):
             self.name = name
             self.age = age

         def speak(self):
             return f"{self.name} says woof!"

     for name, age in [("Rex", 3), ("Bella", 7)]:
         d = Dog(name, age)
         print(d.speak(), f"(age {d.age})")
     """),
    ("Inheritance with Vehicles", "easy",
     "Subclass a base class and extend its behavior.", """
     class Vehicle:
         def __init__(self, make):
             self.make = make

         def describe(self):
             return f"{self.make} vehicle"

     class ElectricCar(Vehicle):
         def __init__(self, make, kwh):
             super().__init__(make)
             self.kwh = kwh

         def describe(self):
             return f"{super().describe()} with {self.kwh} kWh battery"

     print(Vehicle("Generic").describe())
     print(ElectricCar("Meridian", 75).describe())
     """),
    ("Polymorphism with Shapes", "medium",
     "Call the same method on different shape classes.", """
     import math

     class Square:
         def __init__(self, side):
             self.side = side

         def area(self):
             return self.side ** 2

     class Circle:
         def __init__(self, r):
             self.r = r

         def area(self):
             return math.pi * self.r ** 2

     for shape in [Square(4), Circle(3), Square(1.5)]:
         print(f"{type(shape).__name__}: area {shape.area():.2f}")
     """),
    ("Property Getter and Setter", "medium",
     "Guard an attribute with the property decorator.", """
     class Thermostat:
         def __init__(self):
             self._target = 20

         @property
         def target(self):
             return self._target

         @target.setter
         def target(self, value):
             self._target = min(max(value, 5), 30)

     t = Thermostat()
     for v in [18, 55, -10]:
         t.target = v
         print(f"requested {v} -> set to {t.target}")
     """),
    ("classmethod vs staticmethod", "medium",
     "Contrast alternative constructors and utility methods.", """
     class Pizza:
         def __init__(self, toppings):
             self.toppings = toppings

         @classmethod
         def margherita(cls):
             return cls(["tomato", "mozzarella", "basil"])

         @staticmethod
         def is_veggie(topping):
             return topping not in ("ham", "pepperoni")

     p = Pizza.margherita()
     print(f"toppings: {p.toppings}")
     print(f"pepperoni veggie? {Pizza.is_veggie('pepperoni')}")
     print(f"basil veggie? {Pizza.is_veggie('basil')}")
     """),
    ("__str__ vs __repr__", "easy",
     "Give a class friendly and unambiguous string forms.", """
     class Ticket:
         def __init__(self, ident, seat):
             self.ident = ident
             self.seat = seat

         def __str__(self):
             return f"Ticket {self.ident} (seat {self.seat})"

         def __repr__(self):
             return f"Ticket(ident={self.ident!r}, seat={self.seat!r})"

     t = Ticket("A42", "12F")
     print(str(t))
     print(repr(t))
     print([t])
     """),
    ("Operator Overloading with Vector2D", "medium",
     "Support + and * on a small vector class.", """
     class Vec:
         def __init__(self, x, y):
             self.x, self.y = x, y

         def __add__(self, other):
             return Vec(self.x + other.x, self.y + other.y)

         def __mul__(self, k):
             return Vec(self.x * k, self.y * k)

         def __repr__(self):
             return f"Vec({self.x}, {self.y})"

     a, b = Vec(1, 2), Vec(3, -1)
     print(a + b)
     print(a * 3)
     print(a + b * 2)
     """),
    ("Equality and Comparison Dunders", "medium",
     "Implement __eq__ and __lt__ for money values.", """
     class Money:
         def __init__(self, cents):
             self.cents = cents

         def __eq__(self, other):
             return self.cents == other.cents

         def __lt__(self, other):
             return self.cents < other.cents

         def __repr__(self):
             return f"${self.cents / 100:.2f}"

     a, b = Money(499), Money(1250)
     print(f"{a} == {b}: {a == b}")
     print(f"{a} < {b}: {a < b}")
     print(f"max: {max(a, b)}")
     """),
    ("Dataclass Demo", "easy",
     "Cut boilerplate with the dataclass decorator.", """
     from dataclasses import dataclass, field

     @dataclass
     class Task:
         title: str
         done: bool = False
         tags: list = field(default_factory=list)

     t1 = Task("write docs")
     t2 = Task("ship release", True, ["v2"])
     print(t1)
     print(t2)
     print(f"equal? {t1 == Task('write docs')}")
     """),
    ("Abstract Base Class Demo", "hard",
     "Force subclasses to implement required methods with abc.", """
     from abc import ABC, abstractmethod

     class Exporter(ABC):
         @abstractmethod
         def export(self, data):
             ...

     class CSVExporter(Exporter):
         def export(self, data):
             return ",".join(str(d) for d in data)

     class JSONishExporter(Exporter):
         def export(self, data):
             return "[" + ", ".join(str(d) for d in data) + "]"

     for exp in [CSVExporter(), JSONishExporter()]:
         print(f"{type(exp).__name__}: {exp.export([1, 2, 3])}")
     """),
    ("Composition over Inheritance", "medium",
     "Build a Car from an Engine part instead of subclassing.", """
     class Engine:
         def __init__(self, hp):
             self.hp = hp

         def start(self):
             return f"engine ({self.hp} hp) started"

     class Car:
         def __init__(self, name, engine):
             self.name = name
             self.engine = engine

         def start(self):
             return f"{self.name}: {self.engine.start()}"

     print(Car("Roadster", Engine(300)).start())
     print(Car("City Runabout", Engine(90)).start())
     """),
    ("Class vs Instance Variables", "easy",
     "Show how class-level state is shared across instances.", """
     class Counter:
         created = 0

         def __init__(self, name):
             self.name = name
             Counter.created += 1

     a = Counter("a")
     b = Counter("b")
     c = Counter("c")
     print(f"instances created: {Counter.created}")
     print(f"names: {a.name}, {b.name}, {c.name}")
     """),
    ("Custom Iterator Class", "medium",
     "Implement __iter__ and __next__ for a countdown.", """
     class Countdown:
         def __init__(self, start):
             self.current = start

         def __iter__(self):
             return self

         def __next__(self):
             if self.current <= 0:
                 raise StopIteration
             self.current -= 1
             return self.current + 1

     print(list(Countdown(5)))
     for v in Countdown(3):
         print(f"tick {v}")
     """),
    ("Context Manager Class", "medium",
     "Implement __enter__ and __exit__ for a timed block.", """
     class Banner:
         def __init__(self, label):
             self.label = label

         def __enter__(self):
             print(f">>> begin {self.label}")
             return self

         def __exit__(self, exc_type, exc, tb):
             print(f"<<< end {self.label}")
             return False

     with Banner("setup"):
         print("doing work")
     with Banner("teardown"):
         print("cleaning up")
     """),
    ("Singleton Pattern", "hard",
     "Ensure a class only ever has one instance.", """
     class Config:
         _instance = None

         def __new__(cls):
             if cls._instance is None:
                 cls._instance = super().__new__(cls)
                 cls._instance.values = {}
             return cls._instance

     a = Config()
     a.values["env"] = "prod"
     b = Config()
     print(f"same object? {a is b}")
     print(f"b sees: {b.values}")
     """),
    ("Enum-Based State Machine", "hard",
     "Model order states and legal transitions with Enum.", """
     from enum import Enum

     class State(Enum):
         NEW = 1
         PAID = 2
         SHIPPED = 3

     LEGAL = {State.NEW: [State.PAID], State.PAID: [State.SHIPPED], State.SHIPPED: []}

     def advance(state, target):
         ok = target in LEGAL[state]
         print(f"{state.name} -> {target.name}: {'ok' if ok else 'blocked'}")
         return target if ok else state

     s = State.NEW
     s = advance(s, State.PAID)
     s = advance(s, State.SHIPPED)
     advance(s, State.NEW)
     """),
    ("Library Book Tracker Class", "easy",
     "A tiny class exercise for lending library books.", """
     class Book:
         def __init__(self, title):
             self.title = title
             self.on_loan = False

         def check_out(self):
             self.on_loan = True

         def check_in(self):
             self.on_loan = False

     shelf = [Book("Dune"), Book("Emma"), Book("Ulysses")]
     shelf[0].check_out()
     shelf[2].check_out()
     shelf[2].check_in()
     for b in shelf:
         print(f"{b.title}: {'on loan' if b.on_loan else 'available'}")
     """),
    ("Shopping Cart Class", "easy",
     "Add items to a cart and total the order.", """
     class Cart:
         def __init__(self):
             self.items = []

         def add(self, name, price, qty=1):
             self.items.append((name, price, qty))

         def total(self):
             t = 0.0
             for _, price, qty in self.items:
                 t += price * qty
             return t

     cart = Cart()
     cart.add("notebook", 3.50, 2)
     cart.add("pen", 1.25, 4)
     cart.add("desk lamp", 24.99)
     for name, price, qty in cart.items:
         print(f"{qty} x {name} @ ${price:.2f}")
     print(f"total: ${cart.total():.2f}")
     """),
    ("Gradebook Class", "easy",
     "Record scores per student and report averages.", """
     class Gradebook:
         def __init__(self):
             self.scores = {}

         def record(self, student, score):
             self.scores.setdefault(student, []).append(score)

         def average(self, student):
             marks = self.scores[student]
             total = 0
             for m in marks:
                 total += m
             return total / len(marks)

     gb = Gradebook()
     for student, score in [("ana", 88), ("ben", 72), ("ana", 94), ("ben", 80)]:
         gb.record(student, score)
     for student in ["ana", "ben"]:
         print(f"{student}: {gb.average(student):.1f}")
     """),
    ("Bank Wallet Class", "easy",
     "Deposit and withdraw with balance protection.", """
     class Wallet:
         def __init__(self, balance=0.0):
             self.balance = balance

         def deposit(self, amount):
             self.balance += amount

         def withdraw(self, amount):
             if amount > self.balance:
                 print(f"declined: ${amount:.2f} > ${self.balance:.2f}")
             else:
                 self.balance -= amount

     w = Wallet(100)
     w.deposit(50)
     w.withdraw(30)
     w.withdraw(500)
     print(f"final balance: ${w.balance:.2f}")
     """),
    ("Playlist Class", "easy",
     "Queue songs and advance through a playlist.", """
     class Playlist:
         def __init__(self):
             self.songs = []
             self.index = 0

         def add(self, song):
             self.songs.append(song)

         def next_song(self):
             song = self.songs[self.index % len(self.songs)]
             self.index += 1
             return song

     pl = Playlist()
     for s in ["Intro", "Main Theme", "Outro"]:
         pl.add(s)
     for _ in range(4):
         print(f"now playing: {pl.next_song()}")
     """),
    ("Parking Lot Class", "medium",
     "Track spaces in a small parking lot.", """
     class Lot:
         def __init__(self, spaces):
             self.spaces = spaces
             self.parked = []

         def enter(self, plate):
             if len(self.parked) < self.spaces:
                 self.parked.append(plate)
                 return True
             return False

         def leave(self, plate):
             self.parked.remove(plate)

     lot = Lot(2)
     for plate in ["AAA-111", "BBB-222", "CCC-333"]:
         print(f"{plate} enters: {lot.enter(plate)}")
     lot.leave("AAA-111")
     print(f"CCC-333 enters: {lot.enter('CCC-333')}")
     print(f"parked: {lot.parked}")
     """),
]
for title, diff, desc, code in OOP:
    S(title, "oop", diff, desc, code)

# ---------------------------------------------------------------------------
# 16. Parsing & data wrangling (category: parsing)
# ---------------------------------------------------------------------------
PARSE = [
    ("CSV Line Parser", "easy",
     "Split CSV lines into fields, handling simple quoting.", """
     def parse_line(line):
         fields, cur, quoted = [], "", False
         for ch in line:
             if ch == '"':
                 quoted = not quoted
             elif ch == "," and not quoted:
                 fields.append(cur)
                 cur = ""
             else:
                 cur += ch
         fields.append(cur)
         return fields

     rows = ['a,b,c', '"x,y",2,3', 'plain,"quoted words",end']
     for r in rows:
         print(parse_line(r))
     """),
    ("JSON String Reader", "easy",
     "Parse a JSON document and pull out nested values.", """
     import json

     doc = '{"name": "Meridian", "tags": ["dev", "tools"], "meta": {"stars": 42}}'
     data = json.loads(doc)
     print(data["name"])
     print(data["tags"][1])
     print(data["meta"]["stars"])
     """),
    ("JSON Pretty Printer", "easy",
     "Re-indent compact JSON for humans.", """
     import json

     compact = '{"a":1,"b":{"c":[1,2,3]},"d":true}'
     print(json.dumps(json.loads(compact), indent=2))
     """),
    ("Query String Parser", "medium",
     "Parse URL query strings into a dictionary.", """
     def parse_qs(qs):
         out = {}
         for pair in qs.split("&"):
             if "=" in pair:
                 k, v = pair.split("=", 1)
                 out[k] = v
         return out

     for qs in ["page=2&limit=30", "q=hello+world&lang=en&safe="]:
         print(parse_qs(qs))
     """),
    ("Key-Value Config Parser", "medium",
     "Parse an INI-flavored config block with comments.", """
     RAW = \"\"\"# app config
     host = localhost
     port = 8080

     # feature flags
     debug = true\"\"\"

     config = {}
     for line in RAW.splitlines():
         line = line.strip()
         if not line or line.startswith("#"):
             continue
         key, _, value = line.partition("=")
         config[key.strip()] = value.strip()
     print(config)
     """),
    ("Log Line Parser", "medium",
     "Extract level, timestamp, and message from log lines.", """
     import re

     LOGS = ["2026-07-20 09:15:02 INFO server started",
             "2026-07-20 09:15:40 WARN slow request 1250ms",
             "2026-07-20 09:16:01 ERROR db connection lost"]
     pattern = re.compile(r"^(\\S+ \\S+) (\\w+) (.*)$")
     for line in LOGS:
         when, level, msg = pattern.match(line).groups()
         print(f"[{level:<5}] {when} :: {msg}")
     """),
    ("Markdown Heading Extractor", "easy",
     "Pull headings out of a markdown document.", """
     DOC = \"\"\"# Title
     intro text
     ## Install
     pip install thing
     ## Usage
     ### Advanced\"\"\"

     for line in DOC.splitlines():
         if line.startswith("#"):
             level = len(line) - len(line.lstrip("#"))
             print(f"h{level}: {line.lstrip('# ')}")
     """),
    ("HTML Tag Stripper", "medium",
     "Remove markup tags from an HTML fragment with a regex.", """
     import re

     html = "<p>Hello <b>world</b>! Visit <a href='#'>our site</a>.</p>"
     text = re.sub(r"<[^>]+>", "", html)
     print(text)
     """),
    ("Semantic Version Comparator", "medium",
     "Compare version strings component by component.", """
     def newer(a, b):
         pa = [int(x) for x in a.split(".")]
         pb = [int(x) for x in b.split(".")]
         return a if pa > pb else b

     for a, b in [("1.2.10", "1.2.9"), ("2.0.0", "1.99.99"), ("1.0.0", "1.0.0")]:
         print(f"newer of {a} / {b}: {newer(a, b)}")
     """),
    ("Fraction String Calculator", "medium",
     "Do exact arithmetic on fraction strings with fractions.Fraction.", """
     from fractions import Fraction

     pairs = [("1/3", "1/6"), ("3/4", "2/3")]
     for a, b in pairs:
         fa, fb = Fraction(a), Fraction(b)
         print(f"{a} + {b} = {fa + fb}")
         print(f"{a} * {b} = {fa * fb}")
     """),
    ("Duration String Parser", "medium",
     "Parse strings like 1h30m into total minutes.", """
     import re

     def minutes(s):
         total = 0
         for value, unit in re.findall(r"(\\d+)([hms])", s):
             v = int(value)
             if unit == "h":
                 total += v * 60
             elif unit == "m":
                 total += v
             else:
                 total += v / 60
         return total

     for s in ["1h30m", "45m", "2h", "90s"]:
         print(f"{s} -> {minutes(s):g} min")
     """),
    ("Byte Size Humanizer", "easy",
     "Format raw byte counts as KB, MB, or GB.", """
     def humanize(n):
         for unit in ["B", "KB", "MB", "GB", "TB"]:
             if n < 1024:
                 return f"{n:.1f} {unit}"
             n /= 1024
         return f"{n:.1f} PB"

     for n in [512, 2048, 5 * 1024 ** 2, 3 * 1024 ** 3]:
         print(humanize(n))
     """),
    ("Fixed-Width Column Parser", "medium",
     "Slice fixed-width report lines into fields.", """
     LINES = ["0001 widget     19.99",
              "0002 gizmo       4.50",
              "0003 doohickey 129.00"]
     for line in LINES:
         ident = line[0:4]
         name = line[5:14].strip()
         price = float(line[14:].strip())
         print(f"id={ident} name={name!r} price={price}")
     """),
    ("Filter JSON Records", "easy",
     "Keep only records matching a predicate.", """
     import json

     raw = '[{"name":"ana","active":true},{"name":"ben","active":false},{"name":"cal","active":true}]'
     people = json.loads(raw)
     active = [p["name"] for p in people if p["active"]]
     print(f"active users: {active}")
     """),
    ("CSV to JSON Lines", "medium",
     "Convert CSV text to one JSON object per line.", """
     import json

     CSV = \"\"\"name,age,city
     ana,34,Lakeport
     ben,29,Cascadia\"\"\"

     lines = CSV.splitlines()
     headers = lines[0].split(",")
     for line in lines[1:]:
         record = dict(zip(headers, line.split(",")))
         print(json.dumps(record))
     """),
    ("Tabular Report Formatter", "easy",
     "Align a list of dicts into a neat text table.", """
     rows = [{"name": "ana", "score": 88}, {"name": "benjamin", "score": 7},
             {"name": "cal", "score": 100}]
     width = max(len(r["name"]) for r in rows)
     print(f"{'NAME'.ljust(width)}  SCORE")
     for r in rows:
         print(f"{r['name'].ljust(width)}  {r['score']:>5}")
     """),
]
for title, diff, desc, code in PARSE:
    S(title, "parsing", diff, desc, code)

# ---------------------------------------------------------------------------
# 17. Algorithms (category: algorithms) — nothing related to ordering data
# ---------------------------------------------------------------------------
ALG = [
    ("Largest and Second Largest", "easy",
     "Find the two biggest values in one pass.", """
     def top_two(values):
         best = second = float("-inf")
         for v in values:
             if v > best:
                 best, second = v, best
             elif v > second:
                 second = v
         return best, second

     data = [12, 45, 7, 45, 3, 41]
     print(f"data: {data}")
     print(f"top two: {top_two(data)}")
     """),
    ("Edit Distance (Levenshtein)", "hard",
     "Compute the edit distance between two words with DP.", """
     def edit_distance(a, b):
         prev = list(range(len(b) + 1))
         for i, ca in enumerate(a, 1):
             cur = [i]
             for j, cb in enumerate(b, 1):
                 cost = 0 if ca == cb else 1
                 cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
             prev = cur
         return prev[-1]

     for a, b in [("kitten", "sitting"), ("flaw", "lawn"), ("same", "same")]:
         print(f"{a} -> {b}: {edit_distance(a, b)}")
     """),
    ("Longest Common Prefix", "easy",
     "Find the shared prefix of a list of words.", """
     def common_prefix(words):
         prefix = words[0]
         for w in words[1:]:
             while not w.startswith(prefix):
                 prefix = prefix[:-1]
         return prefix

     print(common_prefix(["flower", "flow", "flight"]))
     print(common_prefix(["interspecies", "interstellar", "interstate"]))
     print(repr(common_prefix(["dog", "cat"])))
     """),
    ("Longest Increasing Run", "medium",
     "Find the longest strictly increasing streak in a list.", """
     def longest_run(values):
         best_len, best_start = 1, 0
         run_len, run_start = 1, 0
         for i in range(1, len(values)):
             if values[i] > values[i - 1]:
                 run_len += 1
             else:
                 run_len, run_start = 1, i
             if run_len > best_len:
                 best_len, best_start = run_len, run_start
         return values[best_start:best_start + best_len]

     data = [2, 5, 1, 4, 6, 9, 3, 8]
     print(f"data: {data}")
     print(f"longest run: {longest_run(data)}")
     """),
    ("Majority Element Finder", "medium",
     "Find the majority value using Boyer-Moore voting.", """
     def majority(values):
         candidate, count = None, 0
         for v in values:
             if count == 0:
                 candidate = v
             count += 1 if v == candidate else -1
         return candidate

     data = [3, 1, 3, 3, 2, 3, 3]
     print(f"data: {data}")
     print(f"majority: {majority(data)}")
     """),
    ("Deduplicate Keeping Order", "easy",
     "Remove repeated list items while preserving order.", """
     def dedupe(values):
         seen = set()
         out = []
         for v in values:
             if v not in seen:
                 seen.add(v)
                 out.append(v)
         return out

     print(dedupe([3, 1, 3, 2, 1, 4]))
     print(dedupe(["b", "a", "b", "c", "a"]))
     """),
    ("Flatten Nested Lists (recursive)", "medium",
     "Recursively flatten arbitrarily nested lists.", """
     def flatten(items):
         out = []
         for it in items:
             if isinstance(it, list):
                 out.extend(flatten(it))
             else:
                 out.append(it)
         return out

     print(flatten([1, [2, [3, 4], 5], [[6]], 7]))
     """),
    ("Flatten Nested Lists (stack)", "medium",
     "Flatten nested lists iteratively with an explicit stack.", """
     def flatten(items):
         stack = [items]
         out = []
         while stack:
             cur = stack.pop()
             if isinstance(cur, list):
                 stack.extend(reversed(cur))
             else:
                 out.append(cur)
         return out

     print(flatten([1, [2, [3, 4], 5], [[6]], 7]))
     """),
    ("List Chunker", "easy",
     "Split a list into fixed-size chunks.", """
     def chunks(values, size):
         return [values[i:i + size] for i in range(0, len(values), size)]

     data = list(range(1, 11))
     for size in [3, 4]:
         print(f"size {size}: {chunks(data, size)}")
     """),
    ("Interleave Two Lists", "easy",
     "Merge two lists by alternating their elements.", """
     def interleave(a, b):
         out = []
         for x, y in zip(a, b):
             out.append(x)
             out.append(y)
         out.extend(a[len(b):])
         out.extend(b[len(a):])
         return out

     print(interleave([1, 3, 5], [2, 4, 6]))
     print(interleave(["a", "b"], ["x", "y", "z", "w"]))
     """),
    ("Moving Average Window", "medium",
     "Compute the moving average over a sliding window.", """
     def moving_average(values, k):
         out = []
         total = 0.0
         for i, v in enumerate(values):
             total += v
             if i >= k:
                 total -= values[i - k]
             if i >= k - 1:
                 out.append(round(total / k, 2))
         return out

     data = [10, 20, 30, 40, 50, 60]
     print(f"window 3: {moving_average(data, 3)}")
     """),
    ("Running Total Tracker", "easy",
     "Print cumulative totals as values stream in.", """
     data = [100, -20, 35, -50, 10]
     total = 0
     for v in data:
         total += v
         print(f"{v:+5d} -> balance {total}")
     """),
    ("Fast Power (squaring)", "medium",
     "Compute powers efficiently by repeated squaring.", """
     def fast_pow(base, exp):
         result = 1
         while exp:
             if exp & 1:
                 result *= base
             base *= base
             exp >>= 1
         return result

     for b, e in [(2, 10), (3, 13), (5, 0)]:
         print(f"{b}^{e} = {fast_pow(b, e)}")
     """),
    ("Integer Square Root (Newton)", "medium",
     "Compute integer square roots with Newton's method.", """
     def isqrt_newton(n):
         if n < 2:
             return n
         x = n
         y = (x + 1) // 2
         while y < x:
             x = y
             y = (x + n // x) // 2
         return x

     for n in [0, 15, 16, 1000000, 99980001]:
         print(f"isqrt({n}) = {isqrt_newton(n)}")
     """),
    ("Tower of Hanoi Moves", "hard",
     "Print the moves that solve Tower of Hanoi recursively.", """
     def hanoi(n, source, spare, target):
         if n == 0:
             return
         hanoi(n - 1, source, target, spare)
         print(f"move disk {n}: {source} -> {target}")
         hanoi(n - 1, spare, source, target)

     hanoi(3, "A", "B", "C")
     """),
    ("Josephus Survivor", "hard",
     "Find the surviving position in the Josephus circle.", """
     def josephus(n, k):
         pos = 0
         for size in range(2, n + 1):
             pos = (pos + k) % size
         return pos + 1

     for n, k in [(7, 3), (10, 2), (5, 1)]:
         print(f"n={n}, k={k}: survivor at position {josephus(n, k)}")
     """),
    ("First Unique Character", "easy",
     "Find the first character that appears exactly once.", """
     from collections import Counter

     def first_unique(s):
         counts = Counter(s)
         for i, ch in enumerate(s):
             if counts[ch] == 1:
                 return i, ch
         return -1, None

     for s in ["swiss", "aabb", "coderunner"]:
         print(f"{s}: {first_unique(s)}")
     """),
    ("Missing Value via XOR", "medium",
     "Find the missing value in 0..n using XOR, no arithmetic totals.", """
     def missing(values):
         n = len(values)
         acc = 0
         for i in range(n + 1):
             acc ^= i
         for v in values:
             acc ^= v
         return acc

     print(missing([0, 1, 3, 4]))
     print(missing([4, 2, 1, 0]))
     """),
    ("Single Non-Duplicate via XOR", "easy",
     "Every value appears twice except one; find it with XOR.", """
     def lonely(values):
         acc = 0
         for v in values:
             acc ^= v
         return acc

     print(lonely([2, 3, 5, 3, 2]))
     print(lonely([7, 1, 1]))
     """),
    ("Ordered Intersection of Lists", "easy",
     "List elements common to two lists, in first-list order.", """
     def intersect(a, b):
         bset = set(b)
         return [x for x in a if x in bset]

     print(intersect([1, 2, 3, 4, 5], [5, 3, 9]))
     print(intersect(["x", "y", "z"], ["z", "q"]))
     """),
    ("Longest Palindromic Substring", "hard",
     "Expand around centers to find the longest palindrome inside a string.", """
     def longest_pal(s):
         best = ""
         for center in range(len(s)):
             for lo, hi in [(center, center), (center, center + 1)]:
                 while lo >= 0 and hi < len(s) and s[lo] == s[hi]:
                     lo -= 1
                     hi += 1
                 if hi - lo - 1 > len(best):
                     best = s[lo + 1:hi]
         return best

     for s in ["babad", "cbbd", "forgeeksskeegfor"]:
         print(f"{s}: {longest_pal(s)}")
     """),
    ("Coin Change Ways (DP)", "hard",
     "Count the ways to make an amount from coin denominations.", """
     def ways(amount, coins):
         table = [1] + [0] * amount
         for coin in coins:
             for a in range(coin, amount + 1):
                 table[a] += table[a - coin]
         return table[amount]

     for amount in [5, 12, 27]:
         print(f"{amount} cents: {ways(amount, [1, 5, 10, 25])} ways")
     """),
    ("Greedy Change Maker", "medium",
     "Make change with the fewest US coins greedily.", """
     def change(cents):
         out = {}
         for name, value in [("quarter", 25), ("dime", 10), ("nickel", 5), ("penny", 1)]:
             out[name], cents = divmod(cents, value)
         return out

     for cents in [87, 41, 4]:
         print(f"{cents} cents -> {change(cents)}")
     """),
    ("0/1 Knapsack (DP)", "hard",
     "Choose items to maximize value under a weight cap.", """
     def knapsack(items, cap):
         table = [0] * (cap + 1)
         for weight, value in items:
             for w in range(cap, weight - 1, -1):
                 table[w] = max(table[w], table[w - weight] + value)
         return table[cap]

     items = [(2, 3), (3, 4), (4, 5), (5, 6)]
     for cap in [5, 8]:
         print(f"capacity {cap}: best value {knapsack(items, cap)}")
     """),
    ("Linear Scan Target Finder", "easy",
     "Find the index of a target with a plain linear scan.", """
     def find(values, target):
         for i, v in enumerate(values):
             if v == target:
                 return i
         return -1

     data = [8, 3, 9, 1, 4]
     for target in [9, 1, 7]:
         print(f"find({target}) = {find(data, target)}")
     """),
]
for title, diff, desc, code in ALG:
    S(title, "algorithms", diff, desc, code)

# ---------------------------------------------------------------------------
# 18. Console art patterns (category: basics)
# ---------------------------------------------------------------------------
PAT = [
    ("Star Pyramid Printer", "easy",
     "Print a centered pyramid of stars with nested loops.", """
     n = 5
     for i in range(1, n + 1):
         print(" " * (n - i) + "*" * (2 * i - 1))
     """),
    ("Inverted Star Pyramid", "easy",
     "Print an upside-down pyramid of stars.", """
     n = 5
     for i in range(n, 0, -1):
         print(" " * (n - i) + "*" * (2 * i - 1))
     """),
    ("Hollow Square Pattern", "easy",
     "Print a hollow square border of asterisks.", """
     n = 5
     for r in range(n):
         if r in (0, n - 1):
             print("*" * n)
         else:
             print("*" + " " * (n - 2) + "*")
     """),
    ("Diamond Pattern Printer", "medium",
     "Print a diamond by stacking two pyramids.", """
     n = 4
     for i in range(1, n + 1):
         print(" " * (n - i) + "*" * (2 * i - 1))
     for i in range(n - 1, 0, -1):
         print(" " * (n - i) + "*" * (2 * i - 1))
     """),
    ("Right Triangle Pattern", "easy",
     "Print a right-angled triangle of stars.", """
     for i in range(1, 7):
         print("*" * i)
     """),
    ("Checkerboard Pattern", "easy",
     "Print an alternating checkerboard of X and O.", """
     for r in range(6):
         row = ""
         for c in range(6):
             row += "X" if (r + c) % 2 == 0 else "O"
         print(row)
     """),
    ("Hourglass Pattern", "medium",
     "Print an hourglass shape from stars.", """
     n = 4
     for i in range(n, 0, -1):
         print(" " * (n - i) + "*" * (2 * i - 1))
     for i in range(2, n + 1):
         print(" " * (n - i) + "*" * (2 * i - 1))
     """),
    ("Staircase Pattern", "easy",
     "Print a staircase aligned to the right edge.", """
     n = 5
     for i in range(1, n + 1):
         print(" " * (n - i) + "#" * i)
     """),
    ("Letter X Pattern", "medium",
     "Print a big X using coordinate checks.", """
     n = 7
     for r in range(n):
         row = ""
         for c in range(n):
             row += "*" if c == r or c == n - 1 - r else " "
         print(row)
     """),
    ("Border Box Label", "easy",
     "Print a label inside a drawn box.", """
     label = "CodeRunner"
     width = len(label) + 4
     print("+" + "-" * (width - 2) + "+")
     print("| " + label + " |")
     print("+" + "-" * (width - 2) + "+")
     """),
]
for title, diff, desc, code in PAT:
    S(title, "basics", diff, desc, code)

# ---------------------------------------------------------------------------
# 19. Seeded simulations (category: basics)
# ---------------------------------------------------------------------------
SIM = [
    ("Seeded Dice Roller", "easy",
     "Roll two dice with a fixed seed so runs repeat exactly.", """
     import random

     random.seed(42)
     for roll in range(5):
         a, b = random.randint(1, 6), random.randint(1, 6)
         print(f"roll {roll + 1}: {a} + {b} = {a + b}")
     """),
    ("Seeded Coin Flip Tally", "easy",
     "Flip a fair coin 20 times with a fixed seed and tally results.", """
     import random

     random.seed(7)
     heads = tails = 0
     for _ in range(20):
         if random.random() < 0.5:
             heads += 1
         else:
             tails += 1
     print(f"heads: {heads}")
     print(f"tails: {tails}")
     """),
    ("Seeded Card Dealer", "medium",
     "Shuffle a deck deterministically and deal a hand.", """
     import random

     ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
     suits = ["♠", "♥", "♦", "♣"]
     deck = [r + s for s in suits for r in ranks]
     random.seed(2026)
     random.shuffle(deck)
     print(f"your hand: {deck[:5]}")
     """),
    ("Seeded Lottery Picker", "easy",
     "Pick 6 lottery values from 1-49 with a fixed seed.", """
     import random

     random.seed(99)
     picks = random.sample(range(1, 50), 6)
     print(f"tonight's picks: {picks}")
     """),
    ("Seeded Magic 8-Ball", "easy",
     "Answer questions with deterministic mystic wisdom.", """
     import random

     ANSWERS = ["It is certain", "Ask again later", "Outlook not so good",
                "Signs point to yes", "Very doubtful"]
     random.seed(8)
     for q in ["Will it rain?", "Ship on Friday?", "Rewrite in Rust?"]:
         print(f"Q: {q}")
         print(f"A: {random.choice(ANSWERS)}")
     """),
    ("Rock Paper Scissors Round", "easy",
     "Play three seeded rounds against the computer.", """
     import random

     BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
     random.seed(3)
     for mine in ["rock", "paper", "scissors"]:
         theirs = random.choice(list(BEATS))
         if mine == theirs:
             result = "tie"
         elif BEATS[mine] == theirs:
             result = "win"
         else:
             result = "lose"
         print(f"{mine} vs {theirs}: {result}")
     """),
    ("Seeded Password Maker", "medium",
     "Generate a strong password from a fixed seed.", """
     import random
     import string

     random.seed(1234)
     alphabet = string.ascii_letters + string.digits + "!@#$%"
     pw = "".join(random.choice(alphabet) for _ in range(14))
     print(f"generated: {pw}")
     print(f"length: {len(pw)}")
     """),
]
for title, diff, desc, code in SIM:
    S(title, "basics", diff, desc, code)

# ---------------------------------------------------------------------------
# 20. Stdlib mini-demos (category: basics)
# ---------------------------------------------------------------------------
LIB = [
    ("Enum Weekdays Demo", "easy",
     "Define an Enum and iterate its members.", """
     from enum import Enum

     class Day(Enum):
         MON = 1
         WED = 3
         FRI = 5

     for d in Day:
         print(f"{d.name} = {d.value}")
     print(Day(3))
     """),
    ("Decimal Precision Demo", "medium",
     "Avoid float surprises with the decimal module.", """
     from decimal import Decimal

     print(0.1 + 0.2)
     print(Decimal("0.1") + Decimal("0.2"))
     print(Decimal("1.30") * 3)
     """),
    ("Fractions Module Demo", "easy",
     "Exact rational arithmetic with fractions.Fraction.", """
     from fractions import Fraction

     third = Fraction(1, 3)
     print(third + third + third)
     print(Fraction(0.5))
     print(Fraction("2/8"))
     """),
    ("string Module Constants", "easy",
     "Tour the ready-made character sets in the string module.", """
     import string

     print(string.ascii_lowercase)
     print(string.digits)
     print(string.punctuation[:10])
     print(len(string.printable))
     """),
    ("Type Hints at Runtime", "medium",
     "Inspect annotations stored by type hints.", """
     def greet(name: str, times: int = 1) -> str:
         return ("hello " + name + "! ") * times

     print(greet("world", 2).strip())
     for arg, hint in greet.__annotations__.items():
         print(f"{arg}: {hint.__name__}")
     """),
    ("Simple Assertion Test Harness", "easy",
     "Check a function against expected cases with asserts.", """
     def double(x):
         return x * 2

     CASES = [(2, 4), (0, 0), (-3, -6), ("ab", "abab")]
     for given, expected in CASES:
         actual = double(given)
         status = "PASS" if actual == expected else "FAIL"
         print(f"double({given!r}) == {expected!r}: {status}")
     """),
    ("Retry Loop Simulator", "medium",
     "Simulate retry-with-backoff bookkeeping without waiting.", """
     attempts = ["fail", "fail", "ok"]
     delay = 1
     for i, outcome in enumerate(attempts, 1):
         print(f"attempt {i}: {outcome} (next delay {delay}s)")
         if outcome == "ok":
             print("succeeded!")
             break
         delay *= 2
     """),
    ("Rounding Modes Tour", "easy",
     "Compare round, floor, ceil, and truncation.", """
     import math

     for v in [2.5, 3.5, -2.5, 2.675]:
         print(f"{v}: round={round(v)} floor={math.floor(v)} "
               f"ceil={math.ceil(v)} trunc={math.trunc(v)}")
     """),
]
for title, diff, desc, code in LIB:
    S(title, "basics", diff, desc, code)

# ---------------------------------------------------------------------------
# 21. Physics formulas (category: math)
# ---------------------------------------------------------------------------
PHY = [
    ("Average Speed Calculator", "easy",
     "Compute speed from distance and time.", """
     def speed(distance_km, hours):
         return distance_km / hours

     for d, t in [(150, 2), (42.195, 3.5), (300, 2.5)]:
         print(f"{d} km in {t} h -> {speed(d, t):.1f} km/h")
     """),
    ("Kinetic Energy Calculator", "easy",
     "Compute kinetic energy from mass and velocity.", """
     def kinetic(mass, velocity):
         return 0.5 * mass * velocity ** 2

     for m, v in [(70, 10), (1500, 27.8), (0.145, 40)]:
         print(f"m={m} kg, v={v} m/s: KE = {kinetic(m, v):.1f} J")
     """),
    ("Potential Energy Calculator", "easy",
     "Compute gravitational potential energy near Earth.", """
     G = 9.81

     def potential(mass, height):
         return mass * G * height

     for m, h in [(70, 2), (0.5, 100), (1000, 50)]:
         print(f"m={m} kg, h={h} m: PE = {potential(m, h):.1f} J")
     """),
    ("Force from Mass and Acceleration", "easy",
     "Apply Newton's second law F = ma.", """
     for m, a in [(70, 9.81), (1200, 3), (0.05, 100)]:
         print(f"m={m} kg, a={a} m/s^2: F = {m * a:.1f} N")
     """),
    ("Momentum Calculator", "easy",
     "Compute momentum p = mv for moving objects.", """
     for m, v in [(0.145, 40), (1500, 27.8), (70, 10)]:
         print(f"m={m} kg, v={v} m/s: p = {m * v:.1f} kg*m/s")
     """),
    ("Density Calculator", "easy",
     "Compute density from mass and volume.", """
     for name, mass, volume in [("water", 1000, 1), ("iron", 7874, 1), ("cork", 240, 1)]:
         print(f"{name}: {mass / volume:.0f} kg/m^3")
     """),
    ("Ohm's Law Calculator", "easy",
     "Solve V = IR for each missing quantity.", """
     print(f"V for I=2A, R=10ohm: {2 * 10} V")
     print(f"I for V=12V, R=4ohm: {12 / 4} A")
     print(f"R for V=9V, I=0.5A: {9 / 0.5} ohm")
     """),
    ("Electrical Power Calculator", "easy",
     "Compute power P = VI for appliances.", """
     for name, volts, amps in [("kettle", 230, 10), ("laptop", 20, 3.25), ("LED", 5, 0.02)]:
         print(f"{name}: {volts * amps:.1f} W")
     """),
    ("Free Fall Time and Velocity", "medium",
     "Compute fall time and impact velocity from a height.", """
     import math

     G = 9.81
     for h in [10, 45, 100]:
         t = math.sqrt(2 * h / G)
         v = G * t
         print(f"h={h} m: t={t:.2f} s, v={v:.1f} m/s")
     """),
    ("Wave Speed Calculator", "easy",
     "Compute wave speed from frequency and wavelength.", """
     for freq, length in [(440, 0.784), (2.4e9, 0.125), (50, 6.8)]:
         print(f"f={freq} Hz, wavelength={length} m: v = {freq * length:.1f} m/s")
     """),
    ("Ideal Gas Pressure", "medium",
     "Apply PV = nRT to find pressure.", """
     R = 8.314

     def pressure(n, t_kelvin, volume):
         return n * R * t_kelvin / volume

     for n, t, v in [(1, 273.15, 0.0224), (2, 300, 0.05)]:
         print(f"n={n} mol, T={t} K, V={v} m^3: P = {pressure(n, t, v):.0f} Pa")
     """),
    ("Work Done Calculator", "easy",
     "Compute mechanical work W = Fd.", """
     for force, distance in [(50, 10), (9.81 * 70, 2), (1200, 0.5)]:
         print(f"F={force:.1f} N over {distance} m: W = {force * distance:.1f} J")
     """),
]
for title, diff, desc, code in PHY:
    S(title, "math", diff, desc, code)

# ---------------------------------------------------------------------------
# 22. Variants of gallery classics (safe topics only)
# ---------------------------------------------------------------------------
VAR = [
    ("Factorial (Iterative)", "algorithms", "easy",
     "Compute factorials with a loop instead of recursion.", """
     def factorial(n):
         result = 1
         for i in range(2, n + 1):
             result *= i
         return result

     for n in [0, 5, 10]:
         print(f"{n}! = {factorial(n)}")
     """),
    ("Factorial with math.factorial", "algorithms", "easy",
     "Use the standard library to compute factorials directly.", """
     import math

     for n in [0, 5, 10, 20]:
         print(f"{n}! = {math.factorial(n)}")
     """),
    ("Palindrome Checker (two-pointer)", "strings", "easy",
     "Check palindromes by walking inward from both ends.", """
     def is_palindrome(s):
         s = "".join(c.lower() for c in s if c.isalnum())
         lo, hi = 0, len(s) - 1
         while lo < hi:
             if s[lo] != s[hi]:
                 return False
             lo += 1
             hi -= 1
         return True

     for s in ["racecar", "hello", "No lemon, no melon"]:
         print(f"{s!r}: {is_palindrome(s)}")
     """),
]
for title, cat, diff, desc, code in VAR:
    S(title, cat, diff, desc, code)

# ---------------------------------------------------------------------------
# New users (Meridian Systems accounts) — keep total under 100 rows because
# routes.py loads and rewrites the whole users table on most requests.
# ---------------------------------------------------------------------------
FIRST = ["Maya", "Jordan", "Priya", "Diego", "Elena", "Tomas", "Ingrid",
         "Kenji", "Sofia", "Omar", "Lucas", "Hana", "Felix", "Nadia", "Ravi",
         "Clara", "Mateo", "Yuki", "Amara", "Stefan", "Leila", "Owen", "Zara",
         "Ivan", "Chloe", "Andre", "Bianca", "Hugo", "Farah", "Nikolai",
         "Grace", "Tariq", "Emma", "Rohan", "Alice", "Viktor", "Selin",
         "Dmitri", "Anya", "Carlos", "Mei", "Jonas", "Talia", "Ethan", "Rosa"]
LAST = ["Okafor", "Lindqvist", "Sharma", "Moreau", "Kowalski", "Tanaka",
        "Reyes", "Novak", "Haddad", "Berg", "Costa", "Ivanov", "Nakamura",
        "Fischer", "Osei", "Larsson", "Mehta", "Duval", "Petrova", "Yamamoto",
        "Silva", "Weber", "Rahman", "Johansson", "Delgado", "Bauer", "Nguyen",
        "Kaur", "Brandt", "Rossi", "Vasquez", "Klein", "Ferreira", "Andersen",
        "Malik", "Fontaine", "Sokolov", "Iversen", "Marino", "Chowdhury",
        "Eriksson", "Vargas", "Dubois", "Adeyemi"]
N_NEW_USERS = 90

HISTORY_POOL = [
    ("print(2 + 3)", "5\n"),
    ("for i in range(3):\n    print(i)", "0\n1\n2\n"),
    ("print('hello from CodeRunner')", "hello from CodeRunner\n"),
    ("print(len('coderunner'))", "10\n"),
    ("x = [1, 2, 3]\nprint(x[::-1])", "[3, 2, 1]\n"),
    ("print('-'.join(['a', 'b', 'c']))", "a-b-c\n"),
]

# Queries used by saved annotation tasks — new rows must add ZERO matches.
TASK_QUERIES = ["sort", "sorting", "caesar", "cipher", "fibonacci", "matrix",
                "rotate", "maze", "path", "path planning", "two sum",
                "hashmap", "hash", "sum", "sequence", "trail", "graph",
                "transpose"]


def site_search_matches(rows, q):
    """Replicate routes.index search: substring on title/description/category."""
    ql = q.lower()
    return [r for r in rows if ql in r["title"].lower()
            or ql in r["description"].lower() or ql in r["category"].lower()]


def compute_expected(code):
    """Run code exactly like the site does (python3 -c, cwd=/tmp), twice with
    different hash seeds, to get a stable expected_output."""
    import os
    outs = []
    for seed in ("0", "1"):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
               "PYTHONHASHSEED": seed, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
        r = subprocess.run(["python3", "-c", code], capture_output=True,
                           text=True, timeout=10, cwd="/tmp", env=env)
        assert r.returncode == 0, f"snippet failed (rc={r.returncode}):\n{r.stderr}\n---\n{code}"
        assert r.stderr == "", f"snippet wrote stderr: {r.stderr!r}"
        outs.append(r.stdout)
    assert outs[0] == outs[1], f"nondeterministic output:\n{outs[0]!r}\nvs\n{outs[1]!r}\n---\n{code}"
    assert outs[0], "snippet printed nothing"
    return outs[0]


def build_users(next_id, snippet_ids, existing_usernames):
    users = []
    combos = [(f, l) for f in FIRST for l in LAST]
    rng.shuffle(combos)
    used = set(existing_usernames)
    for first, last in combos:
        if len(users) >= N_NEW_USERS:
            break
        username = f"{first.lower()}_{last.lower()}"
        if username in used:
            continue
        used.add(username)
        low = f"{first} {last}".lower()
        if any(w in low for w in FORBID):
            continue
        saved = rng.sample(snippet_ids, rng.randint(0, 6))
        if rng.random() < 0.35:
            history = []
            for code, stdout in rng.sample(HISTORY_POOL, rng.randint(1, 3)):
                history.append({"code": code, "stdout": stdout,
                                "stderr": "", "returncode": 0})
        else:
            history = []
        users.append({
            "id": next_id + len(users),
            "root_user_id": 0,
            "username": username,
            "password": f"code{rng.randint(100, 999)}!",
            "name": f"{first} {last}",
            "email": f"{first.lower()}.{last.lower()}@meridiansystems.com",
            "saved_snippets": json.dumps(saved),
            "execution_history": json.dumps(history),
        })
    return users


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    existing = [dict(r) for r in db.execute(
        "SELECT id, title, description, category FROM code_editor_execution_snippets")]
    existing_titles = {r["title"] for r in existing}
    next_snip = db.execute(
        "SELECT COALESCE(MAX(id), 0) + 1 FROM code_editor_execution_snippets").fetchone()[0]
    next_user = db.execute(
        "SELECT COALESCE(MAX(id), 0) + 1 FROM code_editor_execution_users").fetchone()[0]
    existing_usernames = [r[0] for r in db.execute(
        "SELECT username FROM code_editor_execution_users")]

    for i, s in enumerate(SNIPS):
        s["id"] = next_snip + i
        assert s["title"] not in existing_titles, f"title collision: {s['title']}"

    # Task-safety: new rows must not match any task-critical search query.
    for q in TASK_QUERIES:
        bad = site_search_matches(SNIPS, q)
        assert not bad, f"query {q!r} would match new: {[b['title'] for b in bad]}"
    assert not any(s["category"] in ("sorting", "projects") for s in SNIPS)

    all_ids = [r["id"] for r in existing] + [s["id"] for s in SNIPS]
    users = build_users(next_user, all_ids, existing_usernames)
    assert len(users) == N_NEW_USERS
    assert len(existing_usernames) + len(users) < 100, "users table must stay <100 rows"

    from collections import Counter
    cats = Counter(s["category"] for s in SNIPS)
    print(f"snippets: +{len(SNIPS)} (ids {SNIPS[0]['id']}..{SNIPS[-1]['id']})")
    print(f"users:    +{len(users)} (ids {users[0]['id']}..{users[-1]['id']})")
    print("categories:", dict(cats))

    if dry:
        for s in SNIPS[:8]:
            print(" ", s["id"], s["category"], s["difficulty"], "|", s["title"])
        print("  ... (--dry-run: skipping expected-output runs and insert)")
        return

    print("computing expected_output for each snippet (runs python3 twice each)...")
    for i, s in enumerate(SNIPS):
        s["expected_output"] = compute_expected(s["code"])
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(SNIPS)} verified")

    bdir = ROOT / "data" / "backups" / "code-editor-execution-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "snippets": [s["id"] for s in SNIPS],
        "users": [u["id"] for u in users]}, indent=1))

    snip_cols = ["id", "title", "language", "code", "description", "category",
                 "difficulty", "expected_output"]
    db.executemany(
        f"INSERT INTO code_editor_execution_snippets ({', '.join(snip_cols)}) "
        f"VALUES ({', '.join('?' * len(snip_cols))})",
        [[s[c] for c in snip_cols] for s in SNIPS])
    user_cols = ["id", "root_user_id", "username", "password", "name", "email",
                 "saved_snippets", "execution_history"]
    db.executemany(
        f"INSERT INTO code_editor_execution_users ({', '.join(user_cols)}) "
        f"VALUES ({', '.join('?' * len(user_cols))})",
        [[u[c] for c in user_cols] for u in users])
    # Keep the external-content FTS index in sync.
    db.execute("INSERT INTO fts_code_editor_execution_snippets"
               "(fts_code_editor_execution_snippets) VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
