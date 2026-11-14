# The AI Daily — publish your live magazine

No coding, paid API, or separate hosting account is needed. GitHub will publish the magazine and refresh the news every day.

## 1. Create your free GitHub repository

1. On a laptop or desktop, visit **https://github.com/signup** to create an account, or sign in.
2. Visit **https://github.com/new**.
3. Set **Repository name** to `the-ai-daily`, select **Public**, then click **Create repository**.
4. Keep the repository empty (do not initialize with a README, gitignore, or license).

## 2. Upload the files — no coding

1. Download and **unzip** `The-AI-Daily-LIVE.zip` on your computer.
2. In GitHub's new repository, select **uploading an existing file**, or **Add file → Upload files**.
3. Drag **the contents of the unzipped folder**, including `index.html`, `data`, `scripts`, `tests`, `START_HERE.md`, and `.github`. Do not upload the ZIP itself.
4. Important on a Mac: `.github` is a hidden folder. In Finder, press **Command + Shift + .** to show hidden files. You *must* include it: `.github/workflows/publish.yml` is the automatic publisher.
5. Confirm you can see the paths `index.html`, `data/edition.js`, `scripts/update.py`, and `.github/workflows/publish.yml` in GitHub's file list.
6. Select **Commit changes** at the bottom of the upload page.

If your browser does not accept whole folders, you can use the free **GitHub Desktop** app (https://desktop.github.com/): choose File → Add Local Repository for the unzipped folder, follow its prompt to create a repository, commit the files, then choose Publish repository. Or connect the GitHub app in ChatGPT so the publishing process can be assisted directly.

## 3. Turn on your public website

1. In your repository, open **Settings → Pages**.
2. Under **Build and deployment → Source**, select **GitHub Actions**.
3. Open **Actions** at the top of the repository.
4. Select **Publish The AI Daily**, and choose **Run workflow → Run workflow** (branch `main`).
5. Open the run to see whether all the steps show green checkmarks. If the first upload caused a failure before Pages was enabled, the manual run resolves that.
6. In **Settings → Pages**, open the public link. It will look like:

   `https://YOUR-USERNAME.github.io/the-ai-daily/`

7. Share that link. Visitors do not need a GitHub account.

## 4. Daily updates

- **Automatically every day:** the workflow is scheduled for **09:17 UTC = 06:17 São Paulo**, though GitHub may delay scheduled jobs.
- **Update immediately:** GitHub → your repository → **Actions → Publish The AI Daily → Run workflow**.
- **What is updated?** Headlines, publisher-provided short RSS excerpts, original article links, AI/Startup/VC/Business categories, vocabulary, simple English exercises, and audio reading scripts.
- **What does “Check for updates” do?** It checks the live edition published on GitHub. It does *not* trigger a backend news fetch; only the scheduled or manual GitHub Action does that.
- **What if a publisher is unavailable?** The system skips that feed and shows a note. If fewer than four eligible articles are collected, the workflow stops instead of publishing a misleading blank edition. The last successfully published edition remains online.

## 5. What this first version cannot do

- The magazine uses **source headlines and RSS excerpts**, not AI-generated full-article summaries. It cannot verify every assertion or claim that it read paywalled stories.
- The two-host “podcast” is **browser text-to-speech** of a scripted headline recap, not professionally recorded audio. Availability and voices depend on the browser.
- RSS sources may change, stop responding, or be blocked. The update schedule is best-effort, not guaranteed minute-precise.
- This first version does not automatically scan every web page or Instagram page in your original source list. **All 23 links from your original My Sources catalog are preserved** as links, whether or not the sites have verified RSS feeds. Additional feeds supply more coverage.
- The preview has been replaced with an empty *launch placeholder* so previously unverified preview stories will not be mistaken for current news. The first successful workflow creates the live edition.
- GitHub Pages on the Free plan requires a **public repository**, so only upload files you are happy to make public. This package contains no personal tokens or API keys.

## Troubleshooting

- **No articles yet:** Make sure GitHub Actions completed successfully. The placeholder will remain until the first successful publishing run.
- **No workflow in Actions:** Verify `.github/workflows/publish.yml` is present in your repository on the `main` branch.
- **Permission/Pages deployment error:** Confirm **Settings → Pages → Source: GitHub Actions**.
- **Feed collection error:** Open the failed run → **Collect and prepare news edition** to inspect publisher failures. You can retry using **Run workflow**.
- **Old content in your browser:** Click **Check for updates**, then refresh the page.
- **Website 404:** Check **Settings → Pages** for the exact address and successful deployment.
- **Save edition permission error:** In **Settings → Actions → General**, check **Workflow permissions**. The workflow needs `contents: write` in order to save its daily edition.
- **Scheduled updates unexpectedly stop:** GitHub can disable scheduled workflows after 60 days without repository activity. Successful daily edition commits provide repository activity, but if updates fail for a long period, revisit **Actions** and re-enable the workflow.

## Technical note (no action needed)

The live edition is built by a Python standard-library script at `scripts/update.py`. No API key, paid SaaS, database, or runtime web server is necessary. The GitHub Actions workflow updates `data/edition.js`, deploys it, and saves the latest successful edition to your repository using a bot account. It does not change the rest of your website. Article links point to publishers or to clearly labeled Google News aggregator results. The source catalog preserves your original links. Sources are attributed and publisher excerpts are intentionally brief.
