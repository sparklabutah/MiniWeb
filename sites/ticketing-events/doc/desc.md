This website is an event ticketing platform for Lakeport, WA, similar to Eventbrite/Ticketmaster. Users can discover local events, purchase tickets, manage bookings, and get event recommendations.

Data source: data_sources/ticketing-events/ — events.json (19 Lakeport events), tickets.json (25 tickets), orders.json (17 orders), users.json. All synthetic data linked to MiniWeb universe.

Real-world model: Eventbrite / Ticketmaster. Event discovery grid with filters, event detail pages with seat/ticket selection, multi-step checkout with promo codes.

Temporal dynamics: Events have specific dates — could simulate approaching/passing events. Current implementation uses static data.

Domain-specific notes: Events span concerts, sports, community, arts, and tech categories in Lakeport. Promo code system for discounts. Wishlist/save functionality for future events.
