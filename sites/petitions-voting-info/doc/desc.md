This website simulates a civic engagement portal for a fictional city (Lakeport, WA), combining features from Change.org (community petitions with signature collection) and vote.org / state-level voter information sites (election tracking, voter registration, polling location lookup).

The site is called "Lakeport Civic Hub" and serves as the central platform for community petitions (create, sign, save, subscribe, share), election information (upcoming and past races, ballot measures, turnout data), and voter services (registration verification, polling locations, deadlines, registration form).

Data source: data_sources/petitions-voting/ -- contains petitions.json, signatures.json, elections.json, voter_info.json, and users.json. All generated data representing the fictional City of Lakeport, Cascadia County, Washington.

Real-world models: Change.org (petition creation and signing flow, signature progress bars, social sharing), vote.org (voter registration lookup, polling place finder), and state/county election authority sites (election results, ballot measure explanations).

The domain does not require temporal simulation -- petitions and elections are static records with status fields (active/won/closed for petitions, upcoming/completed for elections). Mutable state includes signatures, user saved/subscribed lists, and new petition creation.
