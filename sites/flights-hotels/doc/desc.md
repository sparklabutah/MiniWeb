This website is a travel booking platform for flights and hotels, similar to Expedia/Kayak/Google Flights. Users can search for flights by origin/destination/date, browse hotels by city/rating/price, compare options, and make bookings.

Data source: data_sources/flights-hotels/ — flights.json (40 flights with airline, route, price, class), hotels.json (30 hotels with amenities, ratings, pricing), bookings.json (15 user bookings), users.json. Original source: Kaggle US Airline Flight Routes and Fares + TBO Hotels datasets.

Real-world model: Expedia / Google Flights / Kayak. Split-view search interface with flight and hotel tabs, filter sidebar with sliders and checkboxes, comparison tables, and multi-step checkout.

Temporal dynamics: Flight prices and availability could vary with time, but current implementation uses a static snapshot.

Domain-specific notes: Routes include SEA, PDX, SFO, LAX, JFK, ORD hubs. Hotels span major West Coast cities. Promo code system supports discount redemption at checkout.
