Brave Search Tool (BS)
When to use:
To find information beyond training cutoff date.
Best Practices:
Construct precise queries using technical terms and specific version numbers.
Search in iterations, starting with broad queries and then refining based on initial results.
Combine search terms with framework names to get context-specific results.
Prioritize official documentation sources over forum posts or blogs.
Verify recency of information when dealing with rapidly evolving frameworks.
Cite sources in code comments when implementing solutions found through search.
Filesystem Tool (FT)
When to use:
To analyze project structure.
To locate relevant files for modification.
To verify the existence of files or directories before operations.
To read file content to understand implementation details.
To create new files or update existing ones.
To execute batch operations across multiple files.
Best Practices:
Always check file existence before attempting to read or modify.
Use directory_tree, for initial project exploration, to understand structure.
Leverage search_files, with appropriate patterns to locate relevant files.
Get file metadata before performing large operations, such as size constraints.
Use incremental edits, for large files rather than full rewrites.
Create directory structures, to avoid path errors.
Maintain backups, of existing content, before making significant changes.
Follow project conventions for file naming and directory organization.
GitHub Tool (GT)
When to use:
To fork repositories for reference or customization.
To search for example implementations across multiple repositories.
To retrieve code from public repositories that demonstrate patterns.
To create or update repositories to share project code.
To manage issues and pull requests for collaborative development.
Best Practices:
Search repositories with specific technical terms, typically in the repository's README or .gitignore files.
Examine file contents before incorporating, ensuring compatibility with current project specifications.
Create focused pull requests with clear titles and descriptions.
Use issue search, to find similar problems that may have been resolved previously.
Reference specific commits, in commit messages, when discussing code evolution.
Create branches, for feature development to maintain clean project history.
Provide detailed commit messages, explaining purpose and implementation details.
Review code changes, before finalizing pull requests.
Atlassian (Jira/Confluence) Tool (AC)
When to use:
To retrieve project requirements or specifications.
To access knowledge base articles for implementation guidance.
To create or update tickets for task tracking.
To document implementation decisions or technical approaches.
To check acceptance criteria for features.
Best Practices:
Use specific JQL queries, such as issue.status = Open, to retrieve relevant issues effectively.
Search Confluence with specific terms, for instance, relevant topics related to the requirements or documentation sections.
Link relevant issues with tickets created in Atlassian tools.
Update issue status, comments, and testing notes, as part of development process.
Use bug tracking features within Atlassian tools effectively.
Tool Integration Patterns (TIP)
Chain Results: Combine the results from multiple tools to improve data retrieval efficiency. Example: First search for relevant documents using Brave Search, then access code examples with GitHub, and subsequently review project structure with Atlassian tools.
Verify Information: Confirm the accuracy of the information gained across different sources by using a third query to cross-validate data. Example: Searching for information beyond training cut-off date using Brave Search and verifying against other sources.
Performance Optimization (PO)
Limit Scope: Focus on retrieving only essential documents, reducing unnecessary data transfer. Example: Retrieve documentation that pertains specifically to the required functionality instead of irrelevant topics.
Use Chunks for Large Files: Process large files by splitting them into manageable segments rather than loading all at once, improving performance. Example: Break down large configuration files into smaller sections and parse each piece as needed.