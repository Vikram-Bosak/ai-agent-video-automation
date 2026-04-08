# Backup Trigger Setup: cron-job.org

If GitHub Actions' internal scheduler is inconsistent, you can use **cron-job.org** to trigger the agent 24/7.

## Step 1: Create a GitHub Personal Access Token (PAT)
1. Go to **Settings** > **Developer settings** > **Personal access tokens** > **Tokens (classic)**.
2. Click **Generate new token (classic)**.
3. Select the `repo` and `workflow` scopes.
4. Copy the token immediately.

## Step 2: Configure cron-job.org
1. Create a new job on [cron-job.org](https://cron-job.org).
2. **Title**: AI Video Agent Trigger
3. **URL**: `https://api.github.com/repos/Vikram-Bosak/ai-agent-video-automation/actions/workflows/automation.yml/dispatches`
4. **Execution Schedule**: Every 30 minutes (or every hour).
5. **Request Method**: `POST`
6. **Request Body**: `{"ref":"main"}`
7. **Request Headers**:
   - `Accept`: `application/vnd.github+json`
   - `Authorization`: `Bearer YOUR_GITHUB_TOKEN_HERE`
   - `X-GitHub-Api-Version`: `2022-11-28`
   - `User-Agent`: `Cron-Job-Trigger`

## Step 3: Test
Click **Run now** on cron-job.org and check the **Actions** tab on your GitHub repository to see if a new run was triggered.
