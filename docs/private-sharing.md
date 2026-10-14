# Share the draft with a few people

Use **Cloudflare Pages Direct Upload + Cloudflare Access**. Keep the GitHub repository private. Reviewers receive a website URL, enter an allowed email address, and sign in using a code sent to that address. They do not need access to the repository or a Cloudflare account.

Repository visibility and website access are separate settings. Ordinary GitHub Pages hosting can publish a public site from a private repository; GitHub's private Pages feature requires an eligible Enterprise Cloud organization and gives access to repository readers. The Pages workflow in this repository now runs only when manually invoked.

## Prepare the upload

Run:

```bash
python3 scripts/package_site.py
```

The script validates the site and creates two files under `/tmp/phader-share/` by default. Use `--output-dir PATH` to change the location.

- `setup-placeholder.zip`: one empty setup page with no research content.
- `phader-private-preview.zip`: the website, videos, figures, fonts, and playback data. It excludes Git history, source experiment directories, policy checkpoints, repository scripts, and credentials.

Direct Upload accepts a ZIP, so no GitHub integration, public repository, build command, or custom domain is needed. Each included file is below the dashboard's 25 MiB limit.

## Configure restricted access before uploading the draft

1. In Cloudflare, open **Workers & Pages**, create a **Pages** project using **Direct Upload**, and upload only `setup-placeholder.zip`. Cloudflare assigns an address such as `your-project.pages.dev`.
2. In the Pages project, open **Settings → General → Enable access policy**. This initially protects preview deployment addresses only.
3. Select **Manage** for that policy. In **Access → Applications**, configure the generated application. Under **Public hostname**, remove the wildcard `*` from the subdomain field so the application covers `your-project.pages.dev`. Rename the application if needed and save. Leave the path unrestricted so that videos and PDFs require the same login as the page.
4. Return to the Pages project and enable the access policy again to protect `*.your-project.pages.dev` preview URLs. Confirm that Access now lists **two applications**, covering the main address and the preview addresses. Follow Cloudflare's [production and preview protection instructions](https://developers.cloudflare.com/pages/platform/known-issues/#enable-access-on-your-pagesdev-domain).
5. In Cloudflare One, configure [One-time PIN login](https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/one-time-pin/). For **both** applications, set the allowed login method to One-time PIN and the **Allow** policy's **Include → Emails** list to your address and the specific reviewer addresses. Replace the automatically created access rules with this list. Selecting One-time PIN as an identity provider enables login; the email list determines who is authorized.
6. Check the main address and a preview address in a private browser window. Both must require login. An allowed address should reach the setup page; an unlisted address must be denied. Apply the same protection to any custom domain you add later.
7. In the same Pages project, create a new deployment and upload `phader-private-preview.zip`. Verify that the website and a direct video URL, such as `/assets/videos/handover.mp4`, still require login when signed out.
8. Share the main `https://your-project.pages.dev` URL with the selected people. Future updates only require rerunning the packaging script and uploading the new website ZIP to this project.

The ZIP is ready to upload, but no Cloudflare project or access policy has been created by this repository. Access is enforced by Cloudflare, not by the ZIP or JavaScript in the page.

## Official references

- [Cloudflare Pages Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/)
- [Protect preview deployments](https://developers.cloudflare.com/pages/configuration/preview-deployments/)
- [Protect the production address as well](https://developers.cloudflare.com/pages/platform/known-issues/#enable-access-on-your-pagesdev-domain)
- [Cloudflare Access policies](https://developers.cloudflare.com/cloudflare-one/access-controls/policies/)
- [GitHub Pages private-site requirements](https://docs.github.com/en/pages/getting-started-with-github-pages/changing-the-visibility-of-your-github-pages-site)
