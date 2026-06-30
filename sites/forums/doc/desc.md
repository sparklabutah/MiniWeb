This website simulates a Reddit-style community discussion forum. The interface emulates Reddit with subreddits, threaded comments, voting, and user profiles.

Data source: data_sources/reddit-augment/ (overlay format with _overlay_meta, posts, comments, users)
The data uses MiniWeb Universe root entity users mapped to Reddit profiles.

Key features:
- Subreddit-based navigation with post feeds (hot/new/top sorting)
- Threaded comment trees with voting
- User profiles with post/comment karma
- Post creation with subreddit and flair selection
- Direct messaging between users
- Social features: save posts, follow/block users, join subreddits, share posts, report content
- Search by keyword and semantic matching
- Date range filtering on post feeds

Real-world model: Reddit (reddit.com)
No temporal simulation needed -- content is static user-generated content.
