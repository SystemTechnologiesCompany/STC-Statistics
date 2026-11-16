import {createHandler} from './handler.ts';

// No Supabase Auth account is involved: code/token authorization is performed
// by our handler plus the private database transaction. No public admin routes.
Deno.serve(createHandler(name => Deno.env.get(name)));
