// First-start setup for the dev MongoDB. The image runs this once, against an empty data
// directory, after it has created the root user. `make infra-reset` wipes the volumes so
// it runs again.
//
// ADR-0001: seven bounded contexts, one database each. A process gets a user that can
// read and write only the databases of the contexts it hosts.

const CONTEXTS = [
  "identity",
  "content",
  "learning",
  "gamification",
  "speech",
  "tutor",
  "analytics",
];

// Launch processes only. `tutor` has no user until the ai-gateway process exists.
const SERVICES = {
  core: {
    password: process.env.MONGO_CORE_PASSWORD,
    contexts: ["identity", "content", "learning", "gamification", "analytics"],
  },
  speech: {
    password: process.env.MONGO_SPEECH_PASSWORD,
    contexts: ["speech"],
  },
};

function fail(message) {
  throw new Error(`mongo-init: ${message}`);
}

const admin = db.getSiblingDB("admin");

for (const [service, spec] of Object.entries(SERVICES)) {
  if (!spec.password) {
    fail(`no password for service "${service}"; check .env`);
  }
  for (const context of spec.contexts) {
    if (!CONTEXTS.includes(context)) {
      fail(`service "${service}" lists "${context}", which is not a bounded context`);
    }
  }
  admin.createUser({
    user: service,
    pwd: spec.password,
    roles: spec.contexts.map((context) => ({ role: "readWrite", db: context })),
  });
}

// A database only exists once it holds a collection. The marker makes all seven show up
// in `show dbs` and records which process owns each.
for (const context of CONTEXTS) {
  const owner = Object.keys(SERVICES).find((s) => SERVICES[s].contexts.includes(context));
  const database = db.getSiblingDB(context);
  database.createCollection("_context");
  database.getCollection("_context").insertOne({ _id: "owner", context, owner: owner ?? null });
}

print(`mongo-init: created ${CONTEXTS.length} context databases and ${Object.keys(SERVICES).length} service users`);
