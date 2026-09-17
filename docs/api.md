# API reference (v1)

Base: `http://127.0.0.1:8000`. Real-time is a WebSocket at `/v1/ws?token=…`.

## Auth

| Method | Path | Body / notes |
| --- | --- | --- |
| POST | `/v1/auth/register` | `email`, `username`, `password` → `{tokens, user}` |
| POST | `/v1/auth/login` | `email`, `password` → same |
| POST | `/v1/auth/refresh` | refresh token rotation |
| POST | `/v1/auth/forgot` | sends reset + device code |
| POST | `/v1/auth/reset` | code + new password |
| GET | `/v1/auth/devices` | active sessions |
| DELETE | `/v1/auth/devices/{id}` | revoke a session |

## Users

`GET /v1/users/me`, `PATCH /v1/users/me`, `GET /v1/users/{id}`,
`GET /v1/users/search?q=`, `PATCH /v1/users/me/fcm-token`.

## Friends

`POST /v1/friends/requests` (`user_id`, optional `message`),
`GET /v1/friends/requests/incoming`, `…/outgoing`,
`POST /v1/friends/requests/{id}/respond` (`accept`),
`…/{id}/cancel`, `GET /v1/friends`, `DELETE /v1/friends`,
`GET /v1/friends/mutual/{peer_id}`.

## Conversations

`GET /v1/conversations` (list w/ streaks), `POST /v1/conversations` (direct,
`user_id`), `GET /v1/conversations/{id}`,
`POST /v1/conversations/groups`, `PATCH /v1/conversations/{id}/group`,
members add/remove/promote/demote, `POST …/{id}/leave`,
`POST …/{id}/read` (`up_to_message_id`), `POST …/{id}/mute`,
`POST …/{id}/pin`, `DELETE /v1/conversations/{id}` (hide).

## Messages (router prefix `/conversations`)

- `GET /v1/conversations/{id}/messages` — history
- `POST /v1/conversations/{id}/messages` — `{body, client_id}` returns
  `{message, client_id}`
- `POST /v1/conversations/{id}/messages/multipart` — media (voice/image)
- `PATCH /v1/conversations/{id}/messages/{mid}` — edit (`body`)
- `DELETE /v1/conversations/{id}/messages/{mid}` — `delete_for` me/everyone
- `POST /v1/conversations/{id}/messages/{mid}/react` — `{emoji}`
- `POST /v1/conversations/{id}/messages/{mid}/unreact`
- `GET /v1/conversations/messages/search?query=`

## Streaks

`GET /v1/streaks/me`, `PATCH /v1/streaks/me/settings`
(`visible`, `notifications_enabled`, `reminders_enabled`, `freezes_enabled`),
`POST /v1/streaks/{conversation_id}/freeze`.

## Calls (architecture seam)

`POST /v1/calls`, `POST /v1/calls/{id}/answer`, `POST /v1/calls/{id}/end`,
`GET /v1/calls/history`.

## Media

`POST /v1/media` returns an upload URL (`media_url`); multipart upload to the
returned URL; `kind` `voice`/`image`/`video`.

## Notifications

`GET /v1/notifications`, `POST …/read-all`, `POST …/{id}/read`,
`GET …/unread-count`, `GET/PATCH …/preferences`, `POST …/push-token`.