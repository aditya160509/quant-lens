# NSE India API - Deployment Guide

## 🚀 Deployment Options

### Option 1: Docker Compose (Recommended for Production)

The easiest way to deploy with NSE API:

```bash
cd /path/to/quant
docker-compose up -d
```

This starts:

- **nse-api** (port 3001) - stock-nse-india server
- **backend** (port 8000) - Python FastAPI
- **frontend** (port 3000) - Next.js

### Option 2: Direct NSE API (No External Server)

For simpler deployments, use the direct NSE client that calls NSE India's official APIs:

1. Set environment variable:

```bash
export USE_DIRECT_NSE=true
```

2. The backend will call NSE India directly without needing the stock-nse-india server.

**Pros**: No additional container/process needed
**Cons**: NSE India may rate limit or block if requests are too frequent

### Option 3: PM2 (Node.js Process Manager)

On a VPS or cloud server:

```bash
# Install PM2
npm install -g pm2

# Start NSE API
pm2 start "npx stock-nse-india serve --port 3001" --name nse-api

# Save and enable on startup
pm2 save
pm2 startup
```

### Option 4: Systemd Service (Linux)

Create `/etc/systemd/system/nse-api.service`:

```ini
[Unit]
Description=NSE India API Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/app
ExecStart=/usr/bin/npx stock-nse-india serve --port 3001
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl enable nse-api
sudo systemctl start nse-api
```

---

## 🔧 Configuration

### Environment Variables

| Variable         | Default                 | Description                         |
| ---------------- | ----------------------- | ----------------------------------- |
| `NSE_API_BASE`   | `http://localhost:3001` | URL of stock-nse-india server       |
| `USE_DIRECT_NSE` | `false`                 | Set to `true` to use direct NSE API |

### Rate Limits

- **stock-nse-india server**: Internal rate limiting at 3 req/sec
- **Direct NSE API**: 2 req/sec (to avoid NSE blocking)

### Caching

- All responses cached for 60 seconds
- Clear cache: `POST /api/nse/cache/clear`

---

## 📊 Available Endpoints

### Equity Data

- `GET /api/nse/equity/{symbol}` - Stock details
- `GET /api/nse/equity/{symbol}/trade-info` - Trading stats
- `GET /api/nse/equity/{symbol}/options` - Options chain
- `GET /api/nse/equity/{symbol}/corporate` - Corporate info

### Earnings Data

- `GET /api/nse/equity/{symbol}/earnings` - Full earnings data
- `GET /api/nse/earnings/upcoming` - Upcoming earnings calendar
- `GET /api/nse/earnings/history/{symbol}` - Historical earnings

### Market Data

- `GET /api/nse/indices` - All indices
- `GET /api/nse/nifty50` - Nifty 50 data
- `GET /api/nse/gainers-losers` - Top movers
- `GET /api/nse/most-active` - Most active stocks

### Health Check

- `GET /api/nse/health` - API status

---

## 🛠️ Troubleshooting

### NSE API Not Working

1. **Check if server is running**:

```bash
curl http://localhost:3001/
```

2. **Check health**:

```bash
curl http://localhost:8000/api/nse/health
```

3. **Use direct API as fallback**:

```bash
export USE_DIRECT_NSE=true
```

### Rate Limited by NSE

If NSE blocks your IP:

1. Wait 10-15 minutes
2. Reduce request frequency
3. Use a proxy/VPN

### Docker Issues

```bash
# Check logs
docker-compose logs nse-api

# Restart
docker-compose restart nse-api
```

---

## 🌐 Cloud Deployment

### Vercel + Railway

1. Deploy frontend to Vercel
2. Deploy backend + nse-api to Railway
3. Set `NEXT_PUBLIC_API_URL` in Vercel to Railway backend URL

### AWS

1. **ECS/Fargate**: Use docker-compose with `ecs-cli`
2. **EC2**: Use PM2 or systemd
3. **Lambda**: Use direct NSE client (no server needed)

### DigitalOcean

1. Create a Droplet
2. Install Docker
3. Run `docker-compose up -d`

---

## 📝 Notes

- NSE India official APIs may change; the direct client may need updates
- The stock-nse-india package is more reliable as it handles NSE's anti-bot measures
- For production, prefer Docker Compose or PM2 for the stock-nse-india server
