# TODO / Content backlog

Content and polish tasks for the NYKP website. See `README.md` for how to edit
pages and deploy.

- [ ] **Add hyperlinks to the Links page** — `content/en/links.md` currently lists
      clubs, orgs, and equipment suppliers as plain text. Add URLs (Markdown link
      syntax: `[Name](https://…)`).
- [ ] **Add YouTube links to The Game page** — `content/en/game.md`. The theme has a
      `{{</* youtube_enhanced id="VIDEO_ID" */>}}` shortcode for privacy-friendly
      embeds, or use plain Markdown links.
- [ ] **Add missing officer photos** — Secretary (Surasit "Pong" Nithikasem) and
      Officer at Large (Kate Eyerman) currently use `/img/placeholder-headshot.jpg`
      in `content/en/about.md`. Drop real photos in `static/img/team/` (ideally
      ~600×600 so they display large and crisp) and update the two `src` paths.
- [ ] **Review and revise the rest of the text content** — proofread all pages in
      `content/en/` for accuracy and tone; much of it was migrated from the old
      WordPress site and may be out of date.
