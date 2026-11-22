// Account server functions (Django: core/views.py claim_player / delete_account). Both need a signed-in
// account; the bearer token is attached by lib/api.ts.
import { call } from "./api";

/** Links the signed-in account to a game player, adopting this browser's guest progress once. */
export const claimPlayer = (opts: { data: { guestToken?: string } }) => call<{ playerId: string; adoptedGuest: boolean }>("account/claim", opts.data);
export const deleteOwnAccount = () => call<{ deleted: boolean }>("account/delete", {});
