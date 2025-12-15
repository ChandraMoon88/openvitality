# How to Contribute to the Free AI Hospital

First off, thank you for considering contributing. Your help is essential for creating a system that can serve billions of people.

## Code of Conduct
This project and everyone participating in it is governed by a Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior.

- **Be Respectful:** Treat everyone with respect. Healthy debates are encouraged, but kindness is required.
- **No Medical Misinformation:** Spreading unsubstantiated medical claims will result in an immediate and permanent ban. All medical logic must be backed by evidence.
- **Inclusivity:** We are committed to providing a welcoming and inspiring community for all.

## Development Setup

1.  **Fork the repository:** Click the 'Fork' button on the top right of the GitHub page.
2.  **Clone your fork:**
    ```bash
    git clone https://github.com/YOUR_USERNAME/hai.git
    cd hai
    ```
3.  **Create a virtual environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
    ```
4.  **Install dependencies:**
    ```bash
    make install
    ```
5.  **Set up secrets:**
    ```bash
    cp .env.example .env
    # Now, fill in the required API keys and credentials in the .env file.
    ```
6.  **Run the tests:**
    ```bash
    make test
    ```
    If all tests pass, you're ready to start developing!

## Branch Naming Convention
To keep our repository organized, please use the following branch naming conventions:

-   **feature/**: For new features (e.g., `feature/add-spanish-language-support`)
-   **bugfix/**: For fixing bugs (e.g., `bugfix/fix-call-disconnection-issue`)
-   **hotfix/**: For urgent production fixes (e.g., `hotfix/resolve-security-vulnerability`)
-   **docs/**: For documentation changes (e.g., `docs/update-architecture-diagram`)

## Pull Request (PR) Process
1.  **Create a new branch** from `main` using the naming convention above.
2.  **Make your changes.** Ensure your code follows the project's style guides (run `make format` and `make lint`).
3.  **Add or update tests** for your changes. We aim for high test coverage.
4.  **Commit your changes** using the commit message format described below.
5.  **Push your branch** to your fork.
6.  **Submit a Pull Request** to the `main` branch of the original repository.
7.  **Link the PR to an issue** if it resolves one (e.g., "Closes #123").

## Commit Message Format
We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification. This helps in automating changelogs and makes the project history easier to read.

Each commit message consists of a **header**, a **body**, and a **footer**.

```
<type>(<scope>): <subject>
<BLANK LINE>
<body>
<BLANK LINE>
<footer>
```

-   **Type**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.
-   **Scope** (optional): The part of the codebase you're changing (e.g., `api`, `database`, `sip`).
-   **Subject**: A concise description of the change.

**Example:**
```
feat(api): add endpoint for patient history

Adds a new GET /patients/{id}/history endpoint to retrieve
the consultation history for a specific patient. This is secured
and requires practitioner-level authentication.
```

## Medical Contributions
**CRITICAL:** Any Pull Request that adds or modifies medical logic, diagnostic criteria, or treatment suggestions **MUST cite a reputable medical source.**

-   **Acceptable Sources:** World Health Organization (WHO), Centers for Disease Control and Prevention (CDC), National Institutes of Health (NIH), peer-reviewed medical journals (e.g., The Lancet, NEJM), and established clinical guidelines.
-   **Unacceptable Sources:** Blogs, personal websites, social media, or any source without rigorous medical oversight.

Include the citation as a comment in the code and in the Pull Request description.

**Example PR Description:**
> This PR implements the HEART score for chest pain risk stratification, as defined by the American College of Cardiology.
>
> **Source:** [ACC Guideline on Management of Patients With Chest Pain](https://www.ahajournals.org/doi/10.1161/CIR.0000000000001029)

## What NOT to Commit
-   **Patient Data:** Never commit any real or synthetic patient data.
-   **API Keys or Secrets:** Use the `.env` file for all credentials.
-   **Large Binary Files:** Avoid committing large files like audio recordings or models. Use a dedicated storage solution.
-   **IDE/Editor Files:** Ensure your editor-specific files are in the global or project `.gitignore`.

Thank you for helping us build a healthier future for everyone!
