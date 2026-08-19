# The agent library (Google Drive)

If a Google Drive connector is available there is a shared library of working agents in a Drive
folder, conventionally named **`Agent Crafter - Agents`**. Reading one before authoring is the
single highest-leverage thing you can do — they encode house conventions no schema captures.

## Resolving the folder

1. If the user gave you a folder link or id, use it. It wins over everything else.
2. Otherwise search for a folder titled `Agent Crafter - Agents`, then **filter to an exact,
   case-sensitive title match yourself.** Drive's `title =` is fuzzy and also returns
   near-misses — a folder merely called `Agent Crafter` comes back too.
3. More than one exact match → stop and ask which.
4. No match → ask for the link rather than concluding there is no library.

Never hardcode a folder id here or carry one between conversations. Ids are per-user and leak
whose Drive is in use.

## An empty listing does not mean an empty folder

Listing a shared folder returns only files **your authenticated account can see**. Files owned by
a *different* account — the normal case for a link-shared library — come back as nothing at all.
The folder can look completely empty while holding every agent you are about to recreate.

So never treat an empty or short listing as proof. If it looks emptier than the user implied,
say what you can see and ask before uploading. Uploading "the missing agents" into a folder that
already has them silently doubles the library, and duplicate definitions make every future
lookup worse. The same caution applies to updating: if you cannot see an existing
`<AGENT_NAME>.json`, you cannot conclude it is absent.

## Reading

Agents are stored as `application/json`, so use `download_file_content` (returns base64) —
`read_file_content` does not accept JSON. Files run roughly 20 KB to 210 KB, so read the one or
two that resemble the task and never bulk-load the folder.

## Writing

After creating or updating an agent, write the payload back as `<AGENT_NAME>.json` so the library
compounds. If a file of that name exists, update it rather than adding a second copy.

Agent payloads embed whatever the graph contains — system prompts, internal hostnames, config-key
names, routing ids. Treat the library with the same care as the agents themselves.
