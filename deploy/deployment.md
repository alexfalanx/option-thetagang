# Deployment and Monitoring Plan

This document outlines deployment strategies and monitoring approaches for running ThetaGangExpanded in production environments.

## Deployment Options

### Local Execution via Cron

Run the bot directly on a local machine with scheduled execution.

**Setup**:
- Install Python dependencies using `pip install -r requirements.txt` in a virtual environment
- Configure credentials in `.env` file (IBKR account, API keys)
- Set up `thetagang.toml` with desired trading parameters
- Create cron jobs to execute the bot at desired intervals (e.g., hourly during market hours)

**Example cron entry** (runs every hour from 9 AM to 4 PM on weekdays):
```
0 9-16 * * 1-5 cd /path/to/ThetaGangExpanded && /path/to/venv/bin/python -m src.main
```

**Advantages**:
- Simple setup, no additional infrastructure
- Easy to debug and monitor locally
- Low cost (no cloud hosting fees)

**Disadvantages**:
- Requires local machine to be running continuously
- No automatic recovery from crashes
- Manual updates required
- Single point of failure

**Best for**: Initial testing, small accounts, users comfortable with manual oversight

### Docker Container Deployment

Package the bot in a Docker container for consistency and portability.

**Setup**:
- Create a Dockerfile that installs Python, dependencies, and application code
- Build configuration into the image or mount as volumes for flexibility
- Use Docker Compose to manage container lifecycle and environment variables
- Run container with restart policies for automatic recovery

**Advantages**:
- Consistent environment across development and production
- Easy to deploy on any Docker-compatible host (local, cloud, NAS)
- Isolation from host system
- Version control for entire runtime environment

**Disadvantages**:
- Requires Docker knowledge
- Additional layer of complexity
- Container must be rebuilt for code updates (unless using volumes)

**Best for**: Users with Docker experience, deployments across multiple environments, scalable setups

### Cloud Deployment (AWS EC2, Azure VM, GCP Compute)

Host the bot on cloud virtual machines for reliability and remote access.

**Setup**:
- Provision a small VM instance (t2.micro on AWS for low cost)
- Install Python and dependencies
- Configure systemd service or supervisor to keep bot running
- Use cloud scheduler (CloudWatch Events, Azure Functions, GCP Cloud Scheduler) to trigger execution
- Set up security groups/firewalls to allow IBKR API access
- Configure automatic backups and snapshots

**Advantages**:
- High availability (cloud uptime SLAs)
- Remote access from anywhere
- Scalable compute resources if needed
- Integration with cloud monitoring and alerting services

**Disadvantages**:
- Ongoing hosting costs
- Requires cloud platform knowledge
- Network latency to IBKR servers (consider region selection)

**Best for**: Production deployments, larger accounts, users requiring 24/7 availability

### Hybrid Approach

Combine local development with cloud production deployment.

Run backtests and testing locally, deploy live trading to cloud for reliability. Use CI/CD pipelines (GitHub Actions, GitLab CI) to automatically test and deploy code changes to production environments.

## Monitoring and Alerting

Comprehensive monitoring ensures the bot is functioning correctly and alerts on issues.

### Logging Strategy

Implement structured logging for troubleshooting and audit trails.

**Log Levels**:
- **DEBUG**: Detailed diagnostic information (strategy calculations, data fetching)
- **INFO**: Normal operation events (orders placed, positions opened/closed)
- **WARNING**: Unexpected but handled conditions (order rejections, API rate limits)
- **ERROR**: Errors requiring attention (connection failures, configuration issues)

**Log Destinations**:
- Write to rotating log files (daily or size-based rotation)
- Optionally stream to centralized logging services (CloudWatch Logs, Datadog, Splunk)
- Include timestamps, log levels, module names, and contextual data (symbol, order ID)

**Log Content**:
- All trading decisions with rationale (why a put was selected)
- Order submissions, fills, rejections, and cancellations
- Portfolio state snapshots at each run (positions, cash, buying power)
- Error stack traces for debugging
- Performance metrics (execution time, API latency)

### Error Alerting

Receive notifications when critical issues occur.

**Alert Channels**:
- **Email**: Send alerts to configured email addresses using SMTP
- **Slack**: Post messages to a dedicated Slack channel via webhooks
- **SMS**: Use Twilio or SNS for urgent alerts (optional, for critical errors only)

**Alert Triggers**:
- Failed IBKR connection or authentication errors
- Order submission failures (rejected orders, insufficient buying power)
- Risk limit violations detected by risk manager
- Unexpected exceptions or crashes
- No successful execution within expected timeframe (missed runs)
- Margin calls or account warnings from IBKR

**Alert Format**:
Include severity level, timestamp, error message, and relevant context (symbol, order details) for quick triage.

### Performance Metrics

Track key metrics for evaluating bot health and trading performance.

**System Metrics**:
- Uptime and successful execution rate
- API call latency to IBKR and Polygon
- Memory and CPU usage
- Order fill rates (percentage of submitted orders that execute)

**Trading Metrics**:
- Positions opened/closed per day
- Realized and unrealized P&L
- Premium collected over time
- Current buying power utilization
- Number of active positions by symbol

**Export Options**:
- Log metrics to files for manual review
- Expose Prometheus metrics endpoint for scraping
- Push metrics to time-series databases (InfluxDB, TimescaleDB)
- Integrate with dashboards (Grafana for visualization)

### Portfolio Monitoring

Track portfolio health and risk exposure.

**Daily Snapshots**:
- Total portfolio value (net liquidation value)
- Cash balance and margin used
- List of open positions with current P&L
- Greeks exposure (delta, theta, vega) across all positions

**Risk Alerts**:
- Portfolio delta exceeds configured limits
- Concentration in single symbol too high
- Margin usage approaching dangerous levels
- Unexpected large losses in short period

### Audit Trail

Maintain complete records for compliance and analysis.

**Trade Log**:
- Every order submission with parameters (symbol, strike, expiration, action, quantity)
- Order status updates (filled, canceled, rejected)
- Fill prices and commissions
- Strategy decisions leading to each trade

**Configuration Changes**:
- Log whenever configuration files are updated
- Track parameter changes over time for performance attribution

**Data Integrity**:
- Verify portfolio state consistency between bot records and IBKR account
- Flag discrepancies for investigation

## Safety and Best Practices

### Start with Paper Trading

Always begin with an IBKR paper trading account to validate:
- Connectivity and authentication work correctly
- Orders are placed as expected
- Strategy logic behaves appropriately
- Risk controls function properly

Run for at least a week in paper trading before considering live deployment.

### Gradual Rollout

When moving to live trading:
- Start with small position sizes and limited capital allocation
- Trade only 1-2 symbols initially
- Monitor closely for the first week
- Gradually increase allocation as confidence builds

### Kill Switch

Implement emergency stop mechanisms:
- Manual kill switch (configuration flag or file to halt trading)
- Automatic halt if critical errors occur repeatedly
- Ability to close all positions quickly if needed
- Clear documentation on emergency procedures

### Regular Reviews

Schedule periodic reviews of:
- Trading performance vs expectations
- Log files for warnings or errors
- Configuration parameter effectiveness
- Backtest results vs live performance

Adjust strategy parameters based on observed performance and changing market conditions.

### Security Considerations

Protect sensitive credentials and account access:
- Never commit `.env` files or credentials to version control
- Use environment variables or secret management systems (AWS Secrets Manager, HashiCorp Vault)
- Restrict file permissions on configuration files (chmod 600)
- Limit network access to bot host (firewall rules, security groups)
- Enable two-factor authentication on IBKR account
- Regularly rotate API keys

## Deployment Checklist

Before going live:

- [ ] All tests passing (unit, integration, backtests)
- [ ] Configuration validated for production (correct account number, reasonable position sizes)
- [ ] Paper trading successful for at least one week
- [ ] Logging configured and working
- [ ] Alerts set up and tested (send test alert)
- [ ] Monitoring dashboard accessible
- [ ] Emergency stop procedure documented
- [ ] Backup and recovery plan in place
- [ ] Security hardening completed (credentials secured, access restricted)
- [ ] Reviewed recent market conditions for suitability

Following this deployment and monitoring plan ensures reliable, safe, and observable operation of ThetaGangExpanded in production environments.
