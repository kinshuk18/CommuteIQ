-- token_bucket.lua
-- Hand-written Redis Lua script for token-bucket rate limiting.
-- KEYS[1] = bucket key (per-client)
-- ARGV[1] = capacity (max tokens)
-- ARGV[2] = window_seconds (refill period)
-- Returns 1 if request allowed, 0 if denied.
local key      = KEYS[1]
local capacity = tonumber(ARGV[1])
local window   = tonumber(ARGV[2])
local now      = tonumber(redis.call('TIME')[1])  -- unix seconds

local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens     = tonumber(data[1])
local last_refill = tonumber(data[2])

if tokens == nil then
    -- first request from this client
    tokens = capacity - 1
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, window * 2)
    return 1
end

-- refill: one full bucket per window (simple fixed-window refill)
if now - last_refill >= window then
    tokens = capacity - 1
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, window * 2)
    return 1
end

if tokens > 0 then
    redis.call('HSET', key, 'tokens', tokens - 1)
    return 1
end

return 0
