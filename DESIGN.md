# Frontend design

RoleFit Scout is a working interface and a public portfolio demo. Visitors should be able to inspect the resume-to-shortlist workflow immediately, with an explicit distinction between fictional demo output and the self-hosted live application.

The selected direction combines Warm Graphite's practical workspace with Obsidian Editorial's selective serif typography and copper accents. The generated images are visual references, not feature specifications. Preserve the React/Vite stack, existing API contracts, and Python backend.

## Shared rules

- Use IBM Plex Sans for controls and body text, with Georgia reserved for page headings, the candidate name, the selected role, and the search focus. Use warm graphite surfaces and muted copper for actions and selected accents.
- Give related content a continuous shared surface. Keep the result list and detail pane joined, and use a slightly lighter fill for the selected row. Avoid decorative logos, textures, gradients, and oversized scores.
- Keep the demo explanation in one shared notice with a direct GitHub deployment link.
- Use the workflow navigation as the progress indicator. Keep replay and reset in the header's run controls.
- Prefer aligned text and dividers over nested cards, colored callouts, decorative initials, and chips containing sentences.
- Keep a clear next action on each step; preserve visible keyboard focus, inline errors, and explicit empty states.

## Journey

- Resume: input beside a readable profile, with grouped facts and a clear continuation action.
- Preferences: group role/industry and location/eligibility controls; preserve flexible “Any” choices.
- Search brief: labeled rows, with optional editing disclosed inline.
- Strategy: query rows with location and rationale; disclose raw query editing and diagnostics.
- Results: search and optional filters above a match list and detail pane. Stack them on small screens. Hide pagination when all results fit on one page.
- Tracker: one save action, readable rows, stage selection, removal, and navigation back to role details.

Fictional listings must not send demo visitors to placeholder job pages. Live listing links remain available in the live build. Demo fixtures, scoring logic, API routes, and persistence contracts remain backend responsibilities.

## Previous interaction verification

Reviewed all five steps at desktop and 390px mobile width. Exercised profile loading, continuation through preferences/brief/strategy, sample search, detail tabs, filtering and empty results, and tracker add/stage/remove. The changed UI passed Impeccable's mechanical detector. Browser checks use fictional data; they do not exercise live OpenAI or SerpApi services.

## Warm graphite validation

Both the live and static-demo production builds pass TypeScript and Vite compilation. The local demo route returns HTTP 200. This pass changes presentation plus conditional pagination; it adds no controls, API calls, or backend changes. The browser interaction checks above describe the preceding pass, not a new browser test run.
