#!/usr/bin/env python3
"""Build data/dork_catalog.json from WebDorks MIT techniques + generated sets.

Source: https://github.com/root-Manas/webdorks (MIT)
Run from repo root: python scripts/build_dork_catalog.py
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "data", "dork_catalog.json")

# Core / extended / AI blocks adapted from root-Manas/webdorks (MIT).
CORE = [
    {"id": "admin-panels", "title": "Admin Panels Discovery", "description": "Locate exposed administration interfaces across public assets.", "goals": ["recon", "admin-panels"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN intitle:\"admin\" inurl:login"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN (intitle:admin OR inurl:dashboard)"}, {"engine": "Yandex", "q": "host:TARGET_DOMAIN title:admin"}]},
    {"id": "env-leaks", "title": "Environment File Leaks", "description": "Find accidentally exposed .env and secret-bearing config files.", "goals": ["secrets", "misconfigurations"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN ext:env (DB_PASSWORD OR API_KEY)"}, {"engine": "GitHub", "q": "org:ORG_NAME filename:.env (AWS_SECRET_ACCESS_KEY OR PRIVATE_KEY)"}, {"engine": "GitLab", "q": "group:ORG_NAME filename:.env SECRET_KEY"}]},
    {"id": "open-buckets", "title": "Open Bucket Artifacts", "description": "Hunt public cloud bucket listings and object references.", "goals": ["cloud", "data-exposure"], "queries": [{"engine": "Google", "q": "site:s3.amazonaws.com \"TARGET_DOMAIN\""}, {"engine": "Google", "q": "site:storage.googleapis.com \"TARGET_DOMAIN\""}, {"engine": "FOFA", "q": "domain=\"TARGET_DOMAIN\" && body=\"amazonaws.com\""}]},
    {"id": "api-keys", "title": "API Key Exposure", "description": "Surface service tokens, API credentials, and integration secrets.", "goals": ["secrets", "api-security"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (filename:.env OR filename:config) (STRIPE_SECRET OR SENDGRID_API_KEY)"}, {"engine": "Google", "q": "site:TARGET_DOMAIN (\"api_key\" OR \"access_token\") filetype:json"}, {"engine": "PublicWWW", "q": "TARGET_DOMAIN \"AIza\""}]},
    {"id": "js-endpoints", "title": "JavaScript Endpoint Mining", "description": "Discover internal endpoints and hidden routes in JS bundles.", "goals": ["recon", "attack-surface"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN filetype:js (api OR graphql OR token)"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN ext:js \"/api/\""}, {"engine": "GitHub", "q": "org:ORG_NAME language:JavaScript \"/api/\""}]},
    {"id": "graphql", "title": "GraphQL Surface", "description": "Identify GraphQL endpoints and introspection hints.", "goals": ["api-security", "attack-surface"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN inurl:graphql (query OR mutation)"}, {"engine": "Shodan", "q": "http.title:\"GraphQL\" hostname:TARGET_DOMAIN"}, {"engine": "GitHub", "q": "org:ORG_NAME \"/graphql\""}]},
    {"id": "debug-artifacts", "title": "Debug And Backup Files", "description": "Find backups, dumps, and temporary artifacts left in production.", "goals": ["misconfigurations", "data-exposure"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN (ext:bak OR ext:old OR ext:sql OR ext:zip)"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN (\"index of\" AND (backup OR dump))"}, {"engine": "Yandex", "q": "host:TARGET_DOMAIN ext:sql"}]},
    {"id": "documents", "title": "Sensitive Documents", "description": "Search for exposed internal docs containing credentials or strategy.", "goals": ["osint", "data-exposure"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN (filetype:pdf OR filetype:docx OR filetype:xlsx) (confidential OR internal)"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN filetype:xlsx (password OR key)"}, {"engine": "DuckDuckGo", "q": "site:TARGET_DOMAIN filetype:pdf \"do not distribute\""}]},
    {"id": "login-portals", "title": "SSO And Login Portals", "description": "Map identity and authentication entry points.", "goals": ["recon", "identity"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN (inurl:login OR inurl:sso OR inurl:signin)"}, {"engine": "Censys", "q": "services.tls.certificates.leaf_data.names: TARGET_DOMAIN AND services.http.response.html_title: login"}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN title:\"Sign in\""}]},
    {"id": "repo-secrets", "title": "Repository Secret Sprawl", "description": "Correlate user/org activity and leaked credentials in code hosting.", "goals": ["secrets", "supply-chain"], "queries": [{"engine": "GitHub", "q": "user:USERNAME (password OR token OR PRIVATE_KEY)"}, {"engine": "GitHub", "q": "org:ORG_NAME (filename:id_rsa OR filename:.npmrc _auth)"}, {"engine": "GitLab", "q": "group:ORG_NAME (AWS_SECRET OR CI_JOB_TOKEN)"}]},
    {"id": "ci-cd", "title": "CI/CD Exposure", "description": "Detect pipeline files and credentials exposed in automation workflows.", "goals": ["supply-chain", "misconfigurations"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME path:.github/workflows (secrets OR token)"}, {"engine": "GitLab", "q": "group:ORG_NAME filename:.gitlab-ci.yml (AWS OR GCP OR AZURE)"}, {"engine": "Google", "q": "site:TARGET_DOMAIN (jenkinsfile OR .gitlab-ci.yml OR .github/workflows)"}]},
    {"id": "exposed-cameras", "title": "Exposed Cameras And IoT", "description": "Locate publicly reachable IoT control panels and camera feeds.", "goals": ["iot", "asset-discovery"], "queries": [{"engine": "Shodan", "q": "hostname:TARGET_DOMAIN (webcamxp OR \"IP Camera\")"}, {"engine": "FOFA", "q": "domain=\"TARGET_DOMAIN\" && (title=\"webcam\" || body=\"DVR\")"}, {"engine": "Censys", "q": "services.http.response.html_title: (camera OR dvr) AND TARGET_DOMAIN"}]},
    {"id": "subdomain-indexing", "title": "Indexed Subdomain Inventory", "description": "Extract indexed subdomains and forgotten hosts.", "goals": ["recon", "asset-discovery"], "queries": [{"engine": "Google", "q": "site:*.TARGET_DOMAIN -www"}, {"engine": "Bing", "q": "domain:TARGET_DOMAIN -www"}, {"engine": "SecurityTrails", "q": "domain:TARGET_DOMAIN"}]},
    {"id": "email-footprints", "title": "Email Footprints", "description": "Track public email artifacts tied to targets and employees.", "goals": ["osint", "identity"], "queries": [{"engine": "Google", "q": "\"EMAIL\" (paste OR breach OR leak)"}, {"engine": "GitHub", "q": "\"EMAIL\" filename:.env OR filename:config"}, {"engine": "PublicWWW", "q": "\"EMAIL\""}]},
    {"id": "vpn-rdp", "title": "Remote Access Portals", "description": "Identify internet-facing VPN, RDP gateways, and remote console panels.", "goals": ["attack-surface", "identity"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN (inurl:vpn OR inurl:rdweb OR inurl:remote)"}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN (product:Pulse-Secure OR product:Fortinet)"}, {"engine": "Censys", "q": "services.banner: (VPN OR Remote Desktop) AND TARGET_DOMAIN"}]},
    {"id": "k8s-exposure", "title": "Kubernetes Exposure", "description": "Look for public Kubernetes dashboards and config leaks.", "goals": ["cloud", "misconfigurations"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN (kubernetes-dashboard OR kubeconfig)"}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN \"kubernetes\" port:10250"}, {"engine": "GitHub", "q": "org:ORG_NAME filename:kubeconfig"}]},
    {"id": "db-admin-panels", "title": "Database Admin Interfaces", "description": "Find exposed DB admin tools like phpMyAdmin and pgAdmin.", "goals": ["admin-panels", "data-exposure"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN (inurl:phpmyadmin OR inurl:pgadmin)"}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN (http.title:phpMyAdmin OR http.title:pgAdmin)"}, {"engine": "FOFA", "q": "domain=\"TARGET_DOMAIN\" && title=\"phpMyAdmin\""}]},
    {"id": "paste-monitoring", "title": "Paste And Leak Monitoring", "description": "Search leaked pastes and dump references for organization keywords.", "goals": ["osint", "data-exposure"], "queries": [{"engine": "Google", "q": "\"ORG_NAME\" (pastebin OR ghostbin OR justpaste) (password OR token)"}, {"engine": "DuckDuckGo", "q": "\"ORG_NAME\" \"leak\" \"credential\""}, {"engine": "GitHub", "q": "\"ORG_NAME\" \"dump\" \"password\""}]},
    {"id": "network-fingerprints", "title": "Network Fingerprints", "description": "Pivot around IP and ASN metadata to discover associated assets.", "goals": ["asset-discovery", "recon"], "queries": [{"engine": "Shodan", "q": "org:\"ORG_NAME\" net:IP"}, {"engine": "Censys", "q": "autonomous_system.asn: ASN"}, {"engine": "FOFA", "q": "ip=\"IP\" || asn=\"ASN\""}]},
    {"id": "swagger-openapi", "title": "Swagger And OpenAPI Endpoints", "description": "Find API docs endpoints that reveal internal routes and schemas.", "goals": ["api-security", "attack-surface"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN (inurl:swagger OR inurl:openapi OR inurl:api-docs)"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN \"swagger-ui\""}, {"engine": "GitHub", "q": "org:ORG_NAME \"openapi.yaml\""}]},
    {"id": "open-directories", "title": "Open Directory Indexes", "description": "Detect exposed index listings that leak source, backups, or logs.", "goals": ["misconfigurations", "data-exposure"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN intitle:\"index of\" (backup OR log OR db)"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN \"index of /\""}, {"engine": "Yandex", "q": "host:TARGET_DOMAIN \"index of\""}]},
]

EXTENDED = [
    {"id": "jira-discovery", "title": "Jira Exposure Discovery", "description": "Locate publicly indexed Jira boards, tickets, and project metadata.", "goals": ["asset-discovery", "osint"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN inurl:/jira/ (browse OR projects)"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN intitle:Jira"}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN http.title:\"Jira\""}]},
    {"id": "confluence-leaks", "title": "Confluence Data Exposure", "description": "Find exposed Confluence spaces and internal documentation pages.", "goals": ["data-exposure", "osint"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN inurl:confluence (confidential OR internal)"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN intitle:Confluence"}, {"engine": "Yandex", "q": "host:TARGET_DOMAIN \"Confluence\""}]},
    {"id": "kibana-panels", "title": "Kibana And Log Panels", "description": "Identify open observability dashboards that expose logs and stack details.", "goals": ["misconfigurations", "attack-surface"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN inurl:kibana app/kibana"}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN product:Kibana"}, {"engine": "Censys", "q": "services.http.response.body: kibana AND TARGET_DOMAIN"}]},
    {"id": "grafana-panels", "title": "Grafana Panel Exposure", "description": "Discover Grafana instances and dashboards available without auth.", "goals": ["misconfigurations", "data-exposure"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN inurl:grafana intitle:grafana"}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN title:\"Grafana\""}, {"engine": "FOFA", "q": "domain=\"TARGET_DOMAIN\" && title=\"Grafana\""}]},
    {"id": "jenkins-admin", "title": "Jenkins CI Panels", "description": "Track Jenkins endpoints and potentially exposed build metadata.", "goals": ["supply-chain", "attack-surface"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN inurl:jenkins intitle:Dashboard"}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN product:Jenkins"}, {"engine": "Censys", "q": "services.http.response.html_title: Jenkins AND TARGET_DOMAIN"}]},
    {"id": "swagger-files", "title": "OpenAPI File Exposure", "description": "Hunt raw OpenAPI and Swagger specification files.", "goals": ["api-security", "recon"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN (swagger.json OR openapi.json OR openapi.yaml)"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN filetype:yaml openapi"}, {"engine": "GitHub", "q": "org:ORG_NAME filename:openapi.yaml"}]},
    {"id": "postgres-backups", "title": "Database Backup Artifacts", "description": "Search for exposed relational database backup files.", "goals": ["data-exposure", "misconfigurations"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN (ext:sql OR ext:dump) (postgres OR mysql)"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN filetype:sql password"}, {"engine": "Yandex", "q": "host:TARGET_DOMAIN ext:sql"}]},
    {"id": "firebase-tokens", "title": "Firebase Token Exposure", "description": "Locate Firebase credentials and configuration leaks.", "goals": ["secrets", "mobile"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME \"firebase\" \"apiKey\""}, {"engine": "Google", "q": "site:TARGET_DOMAIN \"firebaseio.com\" \"apiKey\""}, {"engine": "GitLab", "q": "group:ORG_NAME firebase apiKey"}]},
    {"id": "sentry-debug", "title": "Sentry DSN Leakage", "description": "Identify leaked Sentry DSN and error monitoring endpoints.", "goals": ["secrets", "application-security"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME \"sentry.io\" \"dsn\""}, {"engine": "Google", "q": "site:TARGET_DOMAIN \"sentry\" \"dsn\""}, {"engine": "PublicWWW", "q": "TARGET_DOMAIN \"sentry.io\""}]},
    {"id": "twilio-keys", "title": "Twilio Credential Leaks", "description": "Find exposed Twilio account SID and auth token references.", "goals": ["secrets", "api-security"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME \"TWILIO_AUTH_TOKEN\" OR \"AC[0-9a-f]{32}\""}, {"engine": "Google", "q": "site:TARGET_DOMAIN \"TWILIO_AUTH_TOKEN\""}, {"engine": "GitLab", "q": "group:ORG_NAME TWILIO_AUTH_TOKEN"}]},
    {"id": "slack-webhooks", "title": "Slack Webhook Exposure", "description": "Detect Slack webhook URLs committed in code and docs.", "goals": ["secrets", "communication"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME \"hooks.slack.com/services/\""}, {"engine": "GitLab", "q": "group:ORG_NAME \"hooks.slack.com/services/\""}, {"engine": "Google", "q": "\"hooks.slack.com/services\" \"ORG_NAME\""}]},
    {"id": "discord-bot-token", "title": "Discord Bot Token Leakage", "description": "Identify exposed Discord bot tokens and config payloads.", "goals": ["secrets", "communication"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME \"discord\" \"token\""}, {"engine": "Google", "q": "site:TARGET_DOMAIN \"discord_token\" OR \"bot token\""}, {"engine": "GitLab", "q": "group:ORG_NAME discord token"}]},
    {"id": "docker-secrets", "title": "Docker Compose Secret Exposure", "description": "Find environment variables and secrets embedded in container files.", "goals": ["supply-chain", "secrets"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME filename:docker-compose.yml (PASSWORD OR SECRET OR TOKEN)"}, {"engine": "GitLab", "q": "group:ORG_NAME filename:docker-compose.yml password"}, {"engine": "Google", "q": "site:TARGET_DOMAIN \"docker-compose.yml\" \"PASSWORD\""}]},
    {"id": "terraform-secrets", "title": "Terraform Secret Exposure", "description": "Map cloud secret leakage through Terraform state and variable files.", "goals": ["cloud", "secrets"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (filename:terraform.tfstate OR filename:*.tfvars) (secret OR key)"}, {"engine": "Google", "q": "site:TARGET_DOMAIN terraform.tfstate"}, {"engine": "GitLab", "q": "group:ORG_NAME terraform.tfstate"}]},
    {"id": "ansible-vault", "title": "Ansible Vault Key Exposure", "description": "Discover leaked Ansible vault passwords and inventory secrets.", "goals": ["cloud", "misconfigurations"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME \"ansible-vault\" \"vault_password\""}, {"engine": "GitLab", "q": "group:ORG_NAME ansible vault_password"}, {"engine": "Google", "q": "site:TARGET_DOMAIN \"ansible-vault\" \"password\""}]},
    {"id": "npm-auth", "title": "NPM Auth Token Exposure", "description": "Locate `.npmrc` authentication leaks and private registry tokens.", "goals": ["secrets", "supply-chain"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME filename:.npmrc _authToken"}, {"engine": "GitLab", "q": "group:ORG_NAME filename:.npmrc _authToken"}, {"engine": "Google", "q": "\"_authToken=\" \"ORG_NAME\""}]},
    {"id": "pypi-token", "title": "PyPI Token Leakage", "description": "Detect Python package publishing tokens in config or workflows.", "goals": ["secrets", "supply-chain"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME \"pypi\" \"token\""}, {"engine": "GitLab", "q": "group:ORG_NAME pypi token"}, {"engine": "Google", "q": "\"pypi\" \"__token__\" \"ORG_NAME\""}]},
    {"id": "aws-iam-keys", "title": "AWS IAM Key Disclosure", "description": "Identify leaked AWS access keys and secret pairs.", "goals": ["cloud", "secrets"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME \"AKIA\" \"AWS_SECRET_ACCESS_KEY\""}, {"engine": "Google", "q": "\"AKIA\" \"TARGET_DOMAIN\""}, {"engine": "GitLab", "q": "group:ORG_NAME AWS_SECRET_ACCESS_KEY"}]},
    {"id": "azure-credentials", "title": "Azure Secret Exposure", "description": "Hunt Azure storage/account credentials and connection strings.", "goals": ["cloud", "secrets"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (AZURE_STORAGE_KEY OR AccountKey=)"}, {"engine": "Google", "q": "site:TARGET_DOMAIN \"AccountKey=\" \"EndpointSuffix=core.windows.net\""}, {"engine": "GitLab", "q": "group:ORG_NAME AZURE_STORAGE_KEY"}]},
    {"id": "gcp-service-keys", "title": "GCP Service Account Keys", "description": "Find exposed GCP service account JSON credentials.", "goals": ["cloud", "secrets"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME \"type\": \"service_account\" \"private_key\""}, {"engine": "Google", "q": "\"type\": \"service_account\" \"project_id\" \"TARGET_DOMAIN\""}, {"engine": "GitLab", "q": "group:ORG_NAME service_account private_key"}]},
    {"id": "rabbitmq-panels", "title": "RabbitMQ Management Exposure", "description": "Locate internet-facing RabbitMQ management portals.", "goals": ["attack-surface", "misconfigurations"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN inurl:15672 \"RabbitMQ Management\""}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN product:RabbitMQ"}, {"engine": "FOFA", "q": "domain=\"TARGET_DOMAIN\" && body=\"RabbitMQ Management\""}]},
    {"id": "elastic-panels", "title": "Elasticsearch Endpoint Discovery", "description": "Find Elasticsearch APIs and clusters exposed to the web.", "goals": ["attack-surface", "data-exposure"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN inurl:9200 _cat/indices"}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN port:9200 product:Elastic"}, {"engine": "Censys", "q": "services.port: 9200 AND TARGET_DOMAIN"}]},
    {"id": "mongodb-open", "title": "Open MongoDB Surface", "description": "Map publicly reachable MongoDB service endpoints.", "goals": ["attack-surface", "data-exposure"], "queries": [{"engine": "Shodan", "q": "hostname:TARGET_DOMAIN port:27017"}, {"engine": "Censys", "q": "services.port: 27017 AND TARGET_DOMAIN"}, {"engine": "FOFA", "q": "domain=\"TARGET_DOMAIN\" && port=\"27017\""}]},
    {"id": "redis-open", "title": "Open Redis Surface", "description": "Detect exposed Redis nodes and management interfaces.", "goals": ["attack-surface", "misconfigurations"], "queries": [{"engine": "Shodan", "q": "hostname:TARGET_DOMAIN port:6379"}, {"engine": "Censys", "q": "services.port: 6379 AND TARGET_DOMAIN"}, {"engine": "FOFA", "q": "domain=\"TARGET_DOMAIN\" && port=\"6379\""}]},
    {"id": "vnc-rdp-ports", "title": "Remote Desktop Services", "description": "Inventory exposed RDP and VNC services across assets.", "goals": ["attack-surface", "asset-discovery"], "queries": [{"engine": "Shodan", "q": "hostname:TARGET_DOMAIN (port:3389 OR port:5900)"}, {"engine": "Censys", "q": "services.port: (3389 OR 5900) AND TARGET_DOMAIN"}, {"engine": "FOFA", "q": "domain=\"TARGET_DOMAIN\" && (port=\"3389\" || port=\"5900\")"}]},
    {"id": "splunk-panels", "title": "Splunk Dashboard Exposure", "description": "Find accessible Splunk interfaces and search endpoints.", "goals": ["misconfigurations", "data-exposure"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN inurl:8000/en-US/app/"}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN product:Splunk"}, {"engine": "FOFA", "q": "domain=\"TARGET_DOMAIN\" && title=\"Splunk\""}]},
    {"id": "wordpress-debug", "title": "WordPress Debug Leakage", "description": "Find WordPress files that reveal credentials or debug traces.", "goals": ["application-security", "misconfigurations"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN (wp-config.php OR debug.log)"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN inurl:wp-content debug.log"}, {"engine": "Yandex", "q": "host:TARGET_DOMAIN wp-config.php"}]},
    {"id": "laravel-debug", "title": "Laravel Debug Exposure", "description": "Locate Laravel debug pages and error traces.", "goals": ["application-security", "misconfigurations"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN \"Whoops, looks like something went wrong\" \"laravel\""}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN \"laravel_session\""}, {"engine": "GitHub", "q": "org:ORG_NAME \"APP_DEBUG=true\""}]},
    {"id": "spring-actuator", "title": "Spring Actuator Endpoints", "description": "Discover exposed Spring Boot actuator and health endpoints.", "goals": ["api-security", "attack-surface"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN inurl:/actuator (health OR env OR metrics)"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN inurl:actuator/env"}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN \"Whitelabel Error Page\" \"actuator\""}]},
    {"id": "phpinfo-files", "title": "PHP Info Exposure", "description": "Identify phpinfo pages leaking system and module configuration.", "goals": ["misconfigurations", "application-security"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN inurl:phpinfo.php \"PHP Version\""}, {"engine": "Bing", "q": "site:TARGET_DOMAIN intitle:phpinfo()"}, {"engine": "Yandex", "q": "host:TARGET_DOMAIN phpinfo.php"}]},
    {"id": "git-metadata", "title": "Git Metadata Exposure", "description": "Find accessible `.git` directories and repository internals.", "goals": ["misconfigurations", "source-exposure"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN inurl:.git/config"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN \".git/HEAD\""}, {"engine": "Yandex", "q": "host:TARGET_DOMAIN .git/config"}]},
    {"id": "svn-metadata", "title": "SVN Metadata Exposure", "description": "Detect `.svn` folders and commit metadata disclosure.", "goals": ["misconfigurations", "source-exposure"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN inurl:.svn/entries"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN \".svn\""}, {"engine": "Yandex", "q": "host:TARGET_DOMAIN .svn/entries"}]},
    {"id": "gitlab-instance-search", "title": "Self-Hosted GitLab Enumeration", "description": "Enumerate self-hosted GitLab instances and project references.", "goals": ["asset-discovery", "recon"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN inurl:users/sign_in \"GitLab\""}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN http.title:\"GitLab\""}, {"engine": "Censys", "q": "services.http.response.html_title: GitLab AND TARGET_DOMAIN"}]},
    {"id": "dev-portals", "title": "Developer Portal Discovery", "description": "Map developer hubs, docs portals, and integration consoles.", "goals": ["recon", "api-security"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN (developer OR developers) (api OR docs)"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN intitle:\"Developer Portal\""}, {"engine": "DuckDuckGo", "q": "site:TARGET_DOMAIN \"API reference\""}]},
    {"id": "status-pages", "title": "Status Page Intelligence", "description": "Locate status pages exposing service names and incident timelines.", "goals": ["osint", "asset-discovery"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN (status OR statuspage) incidents"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN intitle:\"Status Page\""}, {"engine": "SecurityTrails", "q": "domain:TARGET_DOMAIN status"}]},
    {"id": "okta-login-surfaces", "title": "Okta Surface Mapping", "description": "Identify Okta tenant sign-in and app launcher portals.", "goals": ["identity", "recon"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN \"okta\" \"sign in\""}, {"engine": "Bing", "q": "site:TARGET_DOMAIN inurl:okta"}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN \"okta-sign-in\""}]},
    {"id": "vpn-vendor-portals", "title": "Vendor VPN Portals", "description": "Discover exposed vendor-specific VPN login interfaces.", "goals": ["identity", "attack-surface"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN (AnyConnect OR Pulse Secure OR GlobalProtect) login"}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN (product:Pulse-Secure OR product:Palo Alto)"}, {"engine": "FOFA", "q": "domain=\"TARGET_DOMAIN\" && (title=\"GlobalProtect\" || title=\"Pulse Secure\")"}]},
    {"id": "kibana-devtools", "title": "Kibana Dev Tools Access", "description": "Search for exposed Kibana dev console endpoints.", "goals": ["attack-surface", "misconfigurations"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN inurl:app/dev_tools"}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN \"app/kibana#/dev_tools\""}, {"engine": "FOFA", "q": "domain=\"TARGET_DOMAIN\" && body=\"dev_tools\""}]},
    {"id": "adminer-exposure", "title": "Adminer Interface Discovery", "description": "Locate publicly accessible Adminer database login screens.", "goals": ["admin-panels", "data-exposure"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN inurl:adminer.php"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN \"Login - Adminer\""}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN title:Adminer"}]},
    {"id": "prometheus-metrics", "title": "Prometheus Metrics Exposure", "description": "Find open `/metrics` endpoints and Prometheus targets.", "goals": ["misconfigurations", "data-exposure"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN inurl:/metrics \"go_gc_duration_seconds\""}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN \"Prometheus Time Series Collection\""}, {"engine": "Censys", "q": "services.http.response.body: prometheus AND TARGET_DOMAIN"}]},
    {"id": "swagger-ui-cdn", "title": "Swagger UI Surface", "description": "Track hosted swagger UI endpoints and API explorers.", "goals": ["api-security", "recon"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN inurl:swagger-ui.html"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN \"Swagger UI\""}, {"engine": "DuckDuckGo", "q": "site:TARGET_DOMAIN \"Try it out\" \"swagger\""}]},
    {"id": "backup-config-files", "title": "Config Backup Files", "description": "Hunt backup copies of configuration files with secret values.", "goals": ["secrets", "misconfigurations"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN (config.php.bak OR .env.bak OR settings.py.old)"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN ext:bak (config OR env)"}, {"engine": "Yandex", "q": "host:TARGET_DOMAIN ext:old config"}]},
    {"id": "oauth-clients", "title": "OAuth Client Secrets", "description": "Identify leaked OAuth client IDs and client secrets.", "goals": ["secrets", "identity"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (client_secret OR oauth_client_secret)"}, {"engine": "Google", "q": "site:TARGET_DOMAIN \"client_secret\" \"oauth\""}, {"engine": "GitLab", "q": "group:ORG_NAME client_secret oauth"}]},
    {"id": "private-key-hunt", "title": "Private Key Hunt", "description": "Search for PEM, PPK, and key material exposed in repositories.", "goals": ["secrets", "source-exposure"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (filename:id_rsa OR extension:pem PRIVATE KEY)"}, {"engine": "GitLab", "q": "group:ORG_NAME extension:pem \"PRIVATE KEY\""}, {"engine": "Google", "q": "\"BEGIN PRIVATE KEY\" \"ORG_NAME\""}]},
    {"id": "jwt-secret-hunt", "title": "JWT Secret Exposure", "description": "Find signing secrets and JWT debug values.", "goals": ["secrets", "application-security"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (JWT_SECRET OR jwtSecret OR HS256 secret)"}, {"engine": "GitLab", "q": "group:ORG_NAME JWT_SECRET"}, {"engine": "Google", "q": "site:TARGET_DOMAIN \"JWT_SECRET\""}]},
    {"id": "stripe-secret-hunt", "title": "Stripe Secret Key Leakage", "description": "Locate Stripe secret keys and webhook secrets.", "goals": ["secrets", "api-security"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (sk_live_ OR STRIPE_SECRET_KEY)"}, {"engine": "GitLab", "q": "group:ORG_NAME STRIPE_SECRET_KEY"}, {"engine": "Google", "q": "\"sk_live_\" \"ORG_NAME\""}]},
    {"id": "sendgrid-key-hunt", "title": "SendGrid API Key Leakage", "description": "Detect SendGrid credentials and SMTP API tokens.", "goals": ["secrets", "communication"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME \"SENDGRID_API_KEY\""}, {"engine": "GitLab", "q": "group:ORG_NAME SENDGRID_API_KEY"}, {"engine": "Google", "q": "\"SENDGRID_API_KEY\" \"ORG_NAME\""}]},
    {"id": "mailgun-key-hunt", "title": "Mailgun Credential Leakage", "description": "Find exposed Mailgun private API keys.", "goals": ["secrets", "communication"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME \"MAILGUN_API_KEY\""}, {"engine": "GitLab", "q": "group:ORG_NAME MAILGUN_API_KEY"}, {"engine": "Google", "q": "\"MAILGUN_API_KEY\" \"ORG_NAME\""}]},
    {"id": "digitalocean-token-hunt", "title": "DigitalOcean Token Exposure", "description": "Identify leaked DigitalOcean API tokens and secrets.", "goals": ["cloud", "secrets"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (DIGITALOCEAN_TOKEN OR do_token)"}, {"engine": "GitLab", "q": "group:ORG_NAME DIGITALOCEAN_TOKEN"}, {"engine": "Google", "q": "\"DIGITALOCEAN_TOKEN\" \"ORG_NAME\""}]},
    {"id": "vercel-token-hunt", "title": "Vercel Token Exposure", "description": "Discover Vercel deployment token and team secret leakage.", "goals": ["cloud", "supply-chain"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (VERCEL_TOKEN OR vercel token)"}, {"engine": "GitLab", "q": "group:ORG_NAME VERCEL_TOKEN"}, {"engine": "Google", "q": "\"VERCEL_TOKEN\" \"ORG_NAME\""}]},
    {"id": "netlify-token-hunt", "title": "Netlify Token Exposure", "description": "Find Netlify auth tokens and build credentials.", "goals": ["cloud", "supply-chain"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (NETLIFY_AUTH_TOKEN OR NETLIFY_SITE_ID)"}, {"engine": "GitLab", "q": "group:ORG_NAME NETLIFY_AUTH_TOKEN"}, {"engine": "Google", "q": "\"NETLIFY_AUTH_TOKEN\" \"ORG_NAME\""}]},
    {"id": "cloudflare-token-hunt", "title": "Cloudflare Credential Exposure", "description": "Locate leaked Cloudflare API keys and auth tokens.", "goals": ["cloud", "secrets"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (CLOUDFLARE_API_TOKEN OR CF_API_KEY)"}, {"engine": "GitLab", "q": "group:ORG_NAME CLOUDFLARE_API_TOKEN"}, {"engine": "Google", "q": "\"CLOUDFLARE_API_TOKEN\" \"ORG_NAME\""}]},
    {"id": "zendesk-keys", "title": "Zendesk API Token Leakage", "description": "Detect exposed Zendesk API tokens and service credentials.", "goals": ["secrets", "communication"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (ZENDESK_API_TOKEN OR zendesk token)"}, {"engine": "GitLab", "q": "group:ORG_NAME ZENDESK_API_TOKEN"}, {"engine": "Google", "q": "\"ZENDESK_API_TOKEN\" \"ORG_NAME\""}]},
    {"id": "intercom-keys", "title": "Intercom Key Exposure", "description": "Hunt for Intercom API key leaks in app and backend code.", "goals": ["secrets", "application-security"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (INTERCOM_API_KEY OR intercom token)"}, {"engine": "GitLab", "q": "group:ORG_NAME INTERCOM_API_KEY"}, {"engine": "Google", "q": "\"INTERCOM_API_KEY\" \"ORG_NAME\""}]},
    {"id": "algolia-keys", "title": "Algolia Admin Key Leakage", "description": "Locate Algolia admin credentials and search key exposure.", "goals": ["secrets", "api-security"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (ALGOLIA_ADMIN_KEY OR ALGOLIA_API_KEY)"}, {"engine": "GitLab", "q": "group:ORG_NAME ALGOLIA_ADMIN_KEY"}, {"engine": "Google", "q": "\"ALGOLIA_ADMIN_KEY\" \"ORG_NAME\""}]},
    {"id": "github-pat-leaks", "title": "GitHub Personal Access Token Leaks", "description": "Search for exposed GitHub PAT patterns and token references.", "goals": ["github", "secrets"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (ghp_ OR github_pat_) (token OR secret)"}, {"engine": "GitLab", "q": "group:ORG_NAME ghp_ token"}, {"engine": "Google", "q": "\"github_pat_\" \"ORG_NAME\""}]},
    {"id": "github-actions-secrets", "title": "GitHub Actions Secret Misuse", "description": "Hunt workflow files that may expose or echo sensitive values.", "goals": ["github", "supply-chain"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME path:.github/workflows (secrets. OR GITHUB_TOKEN OR echo)"}, {"engine": "GitLab", "q": "group:ORG_NAME \".github/workflows\" secrets"}, {"engine": "Google", "q": "\".github/workflows\" \"ORG_NAME\" \"secrets.\""}]},
    {"id": "github-codeowners-surface", "title": "GitHub CODEOWNERS Mapping", "description": "Enumerate ownership files to map critical code stewardship.", "goals": ["github", "recon"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME filename:CODEOWNERS"}, {"engine": "Google", "q": "site:github.com \"ORG_NAME\" \"CODEOWNERS\""}, {"engine": "GitLab", "q": "group:ORG_NAME CODEOWNERS"}]},
    {"id": "github-release-artifacts", "title": "GitHub Release Artifact Exposure", "description": "Inspect release bundles for debug files and embedded secrets.", "goals": ["github", "supply-chain"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (releases OR release) (debug OR config OR secrets)"}, {"engine": "Google", "q": "site:github.com \"ORG_NAME\" \"releases/download\""}, {"engine": "DuckDuckGo", "q": "site:github.com ORG_NAME releases download"}]},
    {"id": "github-container-registry", "title": "GitHub Container Registry Intel", "description": "Track exposed container metadata and package provenance.", "goals": ["github", "supply-chain"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (ghcr.io OR container registry)"}, {"engine": "Google", "q": "\"ghcr.io\" \"ORG_NAME\""}, {"engine": "GitLab", "q": "group:ORG_NAME ghcr.io"}]},
    {"id": "github-discussions-leaks", "title": "GitHub Discussion Data Leaks", "description": "Find secrets accidentally posted in issues, discussions, and PRs.", "goals": ["github", "osint"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (in:issue OR in:comments) (password OR api_key OR token)"}, {"engine": "Google", "q": "site:github.com \"ORG_NAME\" \"issues\" \"token\""}, {"engine": "DuckDuckGo", "q": "site:github.com ORG_NAME \"pull\" \"secret\""}]},
    {"id": "github-gist-leaks", "title": "GitHub Gist Secret Leaks", "description": "Discover exposed secrets posted in public gists by users.", "goals": ["github", "secrets"], "queries": [{"engine": "GitHub", "q": "user:USERNAME gist (password OR token OR key)"}, {"engine": "Google", "q": "site:gist.github.com \"USERNAME\" \"token\""}, {"engine": "DuckDuckGo", "q": "site:gist.github.com USERNAME password"}]},
    {"id": "github-npmrc-leaks", "title": "GitHub NPMRC Credential Leaks", "description": "Find npm registry auth tokens committed in repos.", "goals": ["github", "secrets"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME filename:.npmrc (_authToken OR _auth)"}, {"engine": "Google", "q": "site:github.com \"ORG_NAME\" \".npmrc\" \"_authToken\""}, {"engine": "GitLab", "q": "group:ORG_NAME filename:.npmrc _authToken"}]},
    {"id": "github-dockerhub-creds", "title": "GitHub Docker Credential Leaks", "description": "Locate Docker login credentials in CI and scripts.", "goals": ["github", "secrets"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (docker login OR DOCKER_PASSWORD)"}, {"engine": "Google", "q": "site:github.com \"ORG_NAME\" \"docker login\" \"-p\""}, {"engine": "GitLab", "q": "group:ORG_NAME docker login password"}]},
    {"id": "github-cicd-misconfig", "title": "GitHub CI Misconfiguration Hunt", "description": "Spot dangerous CI patterns like unchecked scripts and secret prints.", "goals": ["github", "supply-chain"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME path:.github/workflows (curl | bash OR set -x OR printenv)"}, {"engine": "Google", "q": "site:github.com \"ORG_NAME\" \".github/workflows\" \"printenv\""}, {"engine": "GitLab", "q": "group:ORG_NAME workflow printenv"}]},
    {"id": "mongo-uri-leaks", "title": "Mongo URI Exposure", "description": "Find MongoDB connection strings with embedded credentials.", "goals": ["secrets", "data-exposure"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME \"mongodb://\" \"@\""}, {"engine": "GitLab", "q": "group:ORG_NAME mongodb:// @"}, {"engine": "Google", "q": "\"mongodb://\" \"TARGET_DOMAIN\""}]},
    {"id": "postgres-uri-leaks", "title": "Postgres URI Exposure", "description": "Discover PostgreSQL DSN strings containing passwords.", "goals": ["secrets", "data-exposure"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME \"postgres://\" \"@\""}, {"engine": "GitLab", "q": "group:ORG_NAME postgres:// @"}, {"engine": "Google", "q": "\"postgres://\" \"TARGET_DOMAIN\""}]},
    {"id": "ssh-config-leaks", "title": "SSH Config And History Leaks", "description": "Find SSH config files and shell history with credentials.", "goals": ["secrets", "source-exposure"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (filename:.ssh/config OR filename:.bash_history password)"}, {"engine": "GitLab", "q": "group:ORG_NAME .ssh/config"}, {"engine": "Google", "q": "\".bash_history\" \"password\" \"ORG_NAME\""}]},
]

AI = [
    {"id": "openai-api-key-exposure", "title": "OpenAI API Key Exposure", "description": "Identify exposed OpenAI keys and model credentials in code and logs.", "goals": ["ai-security", "secrets"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (OPENAI_API_KEY OR sk-proj- OR sk-live-) NOT example"}, {"engine": "GitLab", "q": "group:ORG_NAME OPENAI_API_KEY"}, {"engine": "Google", "q": "\"OPENAI_API_KEY\" \"ORG_NAME\" -docs -example"}]},
    {"id": "llm-prompt-leaks", "title": "LLM Prompt And System Instruction Leaks", "description": "Find hardcoded system prompts and hidden instruction blocks.", "goals": ["ai-security", "application-security"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (\"system prompt\" OR \"You are ChatGPT\" OR \"assistant instructions\")"}, {"engine": "GitLab", "q": "group:ORG_NAME \"system prompt\""}, {"engine": "Google", "q": "site:TARGET_DOMAIN (\"prompt injection\" OR \"system prompt\")"}]},
    {"id": "rag-index-exposure", "title": "RAG Index Exposure", "description": "Detect exposed vector index stores and retrieval artifacts.", "goals": ["ai-security", "data-exposure"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN (faiss OR chroma OR weaviate OR qdrant) (index OR collection)"}, {"engine": "GitHub", "q": "org:ORG_NAME (chroma.sqlite3 OR faiss.index OR qdrant)"}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN (qdrant OR weaviate)"}]},
    {"id": "langchain-secrets", "title": "LangChain Secret Leakage", "description": "Search for LangChain projects leaking API keys or callback tokens.", "goals": ["ai-security", "secrets"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (langchain AND (OPENAI_API_KEY OR SERPAPI_API_KEY OR ANTHROPIC_API_KEY))"}, {"engine": "GitLab", "q": "group:ORG_NAME langchain OPENAI_API_KEY"}, {"engine": "Google", "q": "\"langchain\" \"OPENAI_API_KEY\" \"ORG_NAME\""}]},
    {"id": "llamaindex-leaks", "title": "LlamaIndex Key Exposure", "description": "Locate LlamaIndex code and config leaks with model credentials.", "goals": ["ai-security", "secrets"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (llama_index OR llamaindex) (api_key OR token)"}, {"engine": "GitLab", "q": "group:ORG_NAME llamaindex api_key"}, {"engine": "Google", "q": "\"llamaindex\" \"api_key\" \"ORG_NAME\""}]},
    {"id": "gradio-streamlit-admin", "title": "Gradio And Streamlit Admin Surface", "description": "Discover public AI demo apps and admin/debug endpoints.", "goals": ["ai-security", "attack-surface"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN (inurl:gradio OR inurl:streamlit) (admin OR debug)"}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN (title:\"Gradio\" OR title:\"Streamlit\")"}, {"engine": "FOFA", "q": "domain=\"TARGET_DOMAIN\" && (title=\"Gradio\" || title=\"Streamlit\")"}]},
    {"id": "ollama-endpoints", "title": "Ollama Endpoint Exposure", "description": "Find exposed Ollama inference endpoints and local model APIs.", "goals": ["ai-security", "attack-surface"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN (inurl:11434 OR \"ollama\")"}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN \"Ollama\" port:11434"}, {"engine": "Censys", "q": "services.port: 11434 AND TARGET_DOMAIN"}]},
    {"id": "vllm-endpoints", "title": "vLLM API Exposure", "description": "Locate public vLLM serving endpoints and OpenAI-compatible routes.", "goals": ["ai-security", "attack-surface"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN (vllm OR \"/v1/chat/completions\")"}, {"engine": "Shodan", "q": "hostname:TARGET_DOMAIN \"vllm\" \"chat/completions\""}, {"engine": "Censys", "q": "services.http.response.body: vllm AND TARGET_DOMAIN"}]},
    {"id": "mcp-server-exposure", "title": "MCP Server Exposure", "description": "Search for exposed Model Context Protocol server configs and endpoints.", "goals": ["ai-security", "supply-chain"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (\"mcpServers\" OR \"model context protocol\" OR \".codex-plugin\")"}, {"engine": "GitLab", "q": "group:ORG_NAME mcpServers"}, {"engine": "Google", "q": "\"mcpServers\" \"ORG_NAME\""}]},
    {"id": "agent-memory-leaks", "title": "Agent Memory Leak Hunt", "description": "Find agent memory dumps, traces, and conversation logs.", "goals": ["ai-security", "data-exposure"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (agent_memory OR memory.json OR conversation_log)"}, {"engine": "Google", "q": "site:TARGET_DOMAIN (agent memory OR conversation log) (json OR txt)"}, {"engine": "GitLab", "q": "group:ORG_NAME conversation_log"}]},
    {"id": "prompt-injection-test-surface", "title": "Prompt Injection Surface Mapping", "description": "Discover endpoints and files commonly targeted for prompt injection tests.", "goals": ["ai-security", "application-security"], "queries": [{"engine": "Google", "q": "site:TARGET_DOMAIN (chatbot OR assistant OR ai) (prompt OR instructions)"}, {"engine": "Bing", "q": "site:TARGET_DOMAIN inurl:chat assistant"}, {"engine": "GitHub", "q": "org:ORG_NAME (prompt injection OR jailbreaking)"}]},
    {"id": "embedding-key-exposure", "title": "Embedding Service Key Exposure", "description": "Track leaked embedding API keys and vector service tokens.", "goals": ["ai-security", "secrets"], "queries": [{"engine": "GitHub", "q": "org:ORG_NAME (EMBEDDING_API_KEY OR embeddings key OR VECTOR_DB_API_KEY)"}, {"engine": "GitLab", "q": "group:ORG_NAME EMBEDDING_API_KEY"}, {"engine": "Google", "q": "\"EMBEDDING_API_KEY\" \"ORG_NAME\""}]},
]

AI_PROVIDERS = [
    ("anthropic", "Anthropic", "ANTHROPIC_API_KEY"),
    ("gemini", "Google Gemini", "GEMINI_API_KEY"),
    ("cohere", "Cohere", "COHERE_API_KEY"),
    ("mistral", "Mistral", "MISTRAL_API_KEY"),
    ("perplexity", "Perplexity", "PERPLEXITY_API_KEY"),
    ("together", "Together AI", "TOGETHER_API_KEY"),
    ("groq", "Groq", "GROQ_API_KEY"),
    ("replicate", "Replicate", "REPLICATE_API_TOKEN"),
    ("huggingface", "Hugging Face", "HF_TOKEN"),
    ("deepseek", "DeepSeek", "DEEPSEEK_API_KEY"),
    ("fireworks", "Fireworks", "FIREWORKS_API_KEY"),
    ("openrouter", "OpenRouter", "OPENROUTER_API_KEY"),
    ("voyage", "Voyage AI", "VOYAGE_API_KEY"),
    ("pinecone", "Pinecone", "PINECONE_API_KEY"),
    ("weaviate", "Weaviate", "WEAVIATE_API_KEY"),
    ("qdrant", "Qdrant", "QDRANT_API_KEY"),
    ("milvus", "Milvus", "MILVUS_TOKEN"),
    ("redis-vector", "Redis Vector", "REDIS_URL"),
    ("supabase-vector", "Supabase Vector", "SUPABASE_SERVICE_ROLE_KEY"),
    ("azure-openai", "Azure OpenAI", "AZURE_OPENAI_API_KEY"),
    ("bedrock", "AWS Bedrock", "AWS_SECRET_ACCESS_KEY"),
    ("vertex-ai", "Vertex AI", "GOOGLE_APPLICATION_CREDENTIALS"),
    ("watsonx", "IBM watsonx", "WATSONX_APIKEY"),
    ("xai", "xAI", "XAI_API_KEY"),
]

AI_FRAMEWORKS = [
    ("langgraph", "LangGraph"),
    ("autogen", "AutoGen"),
    ("crewai", "CrewAI"),
    ("semantic-kernel", "Semantic Kernel"),
    ("haystack", "Haystack"),
    ("dspy", "DSPy"),
    ("phidata", "PhiData"),
    ("litellm", "LiteLLM"),
    ("guidance", "Guidance"),
    ("llamaindex", "LlamaIndex"),
    ("langchain", "LangChain"),
    ("openai-sdk", "OpenAI SDK"),
]

PLATFORMS = [
    ("notion", "Notion", "NOTION_API_KEY", "notion.so"),
    ("airtable", "Airtable", "AIRTABLE_API_KEY", "airtable.com"),
    ("atlassian", "Atlassian", "ATLASSIAN_API_TOKEN", "atlassian.net"),
    ("datadog", "Datadog", "DATADOG_API_KEY", "datadoghq.com"),
    ("newrelic", "New Relic", "NEW_RELIC_API_KEY", "newrelic.com"),
    ("sentry", "Sentry", "SENTRY_AUTH_TOKEN", "sentry.io"),
    ("segment", "Segment", "SEGMENT_WRITE_KEY", "segment.com"),
    ("posthog", "PostHog", "POSTHOG_API_KEY", "posthog.com"),
    ("snowflake", "Snowflake", "SNOWFLAKE_PASSWORD", "snowflakecomputing.com"),
    ("supabase", "Supabase", "SUPABASE_SERVICE_ROLE_KEY", "supabase.co"),
    ("planetscale", "PlanetScale", "PLANETSCALE_PASSWORD", "planetscale.com"),
    ("neon", "Neon", "NEON_API_KEY", "neon.tech"),
    ("clickhouse", "ClickHouse", "CLICKHOUSE_PASSWORD", "clickhouse.com"),
    ("kafka", "Kafka", "KAFKA_SASL_PASSWORD", "kafka"),
    ("rabbitmq", "RabbitMQ", "RABBITMQ_DEFAULT_PASS", "rabbitmq"),
    ("stripe", "Stripe", "STRIPE_SECRET_KEY", "stripe.com"),
    ("paypal", "PayPal", "PAYPAL_CLIENT_SECRET", "paypal.com"),
    ("shopify", "Shopify", "SHOPIFY_API_SECRET", "shopify.com"),
    ("cloudinary", "Cloudinary", "CLOUDINARY_URL", "cloudinary.com"),
    ("fastly", "Fastly", "FASTLY_API_KEY", "fastly.com"),
]


def tag_source(items: list[dict], source: str = "webdorks") -> list[dict]:
    out = []
    for item in items:
        row = dict(item)
        row["source"] = source
        out.append(row)
    return out


def gen_providers() -> list[dict]:
    rows = []
    for key, name, token in AI_PROVIDERS:
        rows.append({
            "id": f"ai-provider-{key}",
            "title": f"{name} Credential Exposure",
            "description": f"Discover leaked {name} credentials and integration secrets.",
            "goals": ["ai-security", "secrets"],
            "source": "webdorks",
            "queries": [
                {"engine": "GitHub", "q": f'org:ORG_NAME ({token} OR "{name}" OR {key})'},
                {"engine": "GitLab", "q": f"group:ORG_NAME {token}"},
                {"engine": "Google", "q": f'"{token}" "ORG_NAME" -example -docs'},
            ],
        })
    return rows


def gen_frameworks() -> list[dict]:
    rows = []
    for key, name in AI_FRAMEWORKS:
        rows.append({
            "id": f"ai-framework-{key}",
            "title": f"{name} Secret And Config Hunt",
            "description": f"Inspect {name} projects for prompt/config leaks and hardcoded keys.",
            "goals": ["ai-security", "application-security"],
            "source": "webdorks",
            "queries": [
                {"engine": "GitHub", "q": f'org:ORG_NAME ({key} OR "{name}") (api_key OR token OR secret)'},
                {"engine": "GitLab", "q": f"group:ORG_NAME {key} api_key"},
                {"engine": "Google", "q": f'"{name}" "ORG_NAME" ("api_key" OR "secret")'},
            ],
        })
    return rows


def gen_platforms() -> list[dict]:
    rows = []
    for key, name, token, marker in PLATFORMS:
        rows.append({
            "id": f"platform-{key}-exposure",
            "title": f"{name} Secret Exposure",
            "description": f"Find leaked {name} secrets, tokens, and config artifacts.",
            "goals": ["secrets", "platform-security"],
            "source": "webdorks",
            "queries": [
                {"engine": "GitHub", "q": f'org:ORG_NAME ({token} OR "{name}" OR {marker})'},
                {"engine": "GitLab", "q": f"group:ORG_NAME {token}"},
                {"engine": "Google", "q": f'"{token}" "ORG_NAME" -example -docs'},
            ],
        })
    return rows


def main() -> int:
    catalog = (
        tag_source(CORE)
        + tag_source(EXTENDED)
        + tag_source(AI)
        + gen_providers()
        + gen_frameworks()
        + gen_platforms()
    )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    payload = {
        "attribution": "WebDorks core catalog © root-Manas — MIT License (https://github.com/root-Manas/webdorks)",
        "techniques": catalog,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(catalog)} techniques -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
