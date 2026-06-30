This website simulates a research project landing page for an academic paper (similar to projectpage.github.io, project homepages on institutional sites). It presents the FlowNet paper (ICML 2025) by Alex Rivera and Aisha Patel from Meridian Systems.

The site features a paper overview with abstract, motivation, method, and results sections; a team page; downloadable resources (PDF, slides, poster, code, dataset, video, supplementary, blog post); project updates/news; statistics tables; a search function; citation export in BibTeX/APA/JSON/CSV formats; and a section navigation dropdown.

Data sources:
- data_sources/project-homepages/project.json — project metadata, sections, authors, keywords
- data_sources/project-homepages/resources.json — downloadable resources list
- data_sources/project-homepages/users.json — team member profiles

Real-world model: Academic project homepages like projectpage.github.io, nerfies.github.io, or institutional paper landing pages that accompany published papers.

Temporal dynamics: Static. Project homepages are published once and updated rarely. No temporal simulation needed.

Domain notes: The site is a single-project homepage (not a multi-paper database). All content revolves around one paper. Navigation is between sections of the project (abstract, method, results, etc.) rather than between different papers.
