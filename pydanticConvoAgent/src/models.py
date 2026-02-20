"""
Pydantic models for CyberBud data structures.
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class Message(BaseModel):
    """A chat message."""
    id: Optional[int] = None
    session_id: int
    role: str  # 'user' or 'assistant'
    content: str
    created_at: Optional[datetime] = None


class Session(BaseModel):
    """A study session."""
    id: Optional[int] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    summary: Optional[str] = None
    message_count: int = 0


class Concept(BaseModel):
    """A cybersecurity concept that has been discussed."""
    id: Optional[int] = None
    name: str
    category: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    times_discussed: int = 1


# Cybersecurity concept categories and keywords for extraction
CONCEPT_KEYWORDS = {
    "Threat Intelligence": [
        "IOC", "indicator of compromise", "threat feed", "STIX", "TAXII",
        "threat actor", "APT", "advanced persistent threat", "TTP",
        "tactics techniques procedures", "campaign", "threat hunting"
    ],
    "Cryptography": [
        "hash", "hashing", "MD5", "SHA", "SHA-256", "SHA-1",
        "encryption", "decryption", "AES", "RSA", "symmetric", "asymmetric",
        "public key", "private key", "certificate", "TLS", "SSL", "PKI",
        "digital signature", "cipher", "plaintext", "ciphertext"
    ],
    "Network Security": [
        "firewall", "IDS", "IPS", "intrusion detection", "intrusion prevention",
        "VPN", "proxy", "DMZ", "network segmentation", "VLAN",
        "packet", "protocol", "TCP", "UDP", "IP address", "port",
        "DNS", "DHCP", "NAT", "router", "switch"
    ],
    "Malware": [
        "malware", "virus", "worm", "trojan", "ransomware", "spyware",
        "adware", "rootkit", "botnet", "backdoor", "keylogger",
        "payload", "exploit", "zero-day", "0day"
    ],
    "Authentication": [
        "authentication", "authorization", "MFA", "2FA", "multi-factor",
        "password", "credential", "SSO", "single sign-on", "OAuth",
        "SAML", "token", "session", "identity", "IAM", "RBAC"
    ],
    "Frameworks & Standards": [
        "NIST", "MITRE ATT&CK", "ATT&CK", "ISO 27001", "CIS Controls",
        "SOC 2", "PCI DSS", "HIPAA", "GDPR", "compliance",
        "framework", "standard", "policy", "procedure", "control"
    ],
    "Incident Response": [
        "incident response", "IR", "forensics", "DFIR", "triage",
        "containment", "eradication", "recovery", "lessons learned",
        "playbook", "SIEM", "SOC", "security operations", "alert"
    ],
    "Vulnerabilities": [
        "vulnerability", "CVE", "patch", "exploit", "buffer overflow",
        "SQL injection", "XSS", "cross-site scripting", "CSRF",
        "RCE", "remote code execution", "privilege escalation",
        "OWASP", "penetration testing", "pentest", "bug bounty"
    ],
    "Cloud Security": [
        "cloud security", "AWS", "Azure", "GCP", "S3 bucket",
        "IAM policy", "security group", "container", "Docker", "Kubernetes",
        "serverless", "shared responsibility", "cloud native"
    ],
    "Social Engineering": [
        "phishing", "spear phishing", "vishing", "smishing", "pretexting",
        "social engineering", "baiting", "tailgating", "impersonation",
        "business email compromise", "BEC"
    ]
}


def extract_concepts(text: str) -> list[tuple[str, str]]:
    """
    Extract cybersecurity concepts from text.
    Returns list of (concept_name, category) tuples.
    """
    found = []
    text_lower = text.lower()

    for category, keywords in CONCEPT_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text_lower:
                # Use the keyword as the concept name (preserving case from definition)
                found.append((keyword, category))

    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for item in found:
        if item[0].lower() not in seen:
            seen.add(item[0].lower())
            unique.append(item)

    return unique
