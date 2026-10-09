from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_DATA_DIR = PROJECT_ROOT / "03_Test_Data"


TEST_CASES = {
    "JOB-TEST-003_DATA_ANALYST_raw.txt": """
Data Analyst

NorthStar Retail Analytics Pte. Ltd.

Location: Singapore
Employment type: Full time
Salary: S$4,500 - S$6,000 per month
Posted: 1d ago

Work arrangement: Hybrid, with three days per week in the office.

### Responsibilities

- Analyse sales, customer, and operational data to identify trends and business opportunities.
- Build and maintain dashboards using Power BI.
- Write SQL queries to extract, transform, and validate data.
- Work with business stakeholders to define reporting requirements and KPIs.
- Perform data quality checks and investigate inconsistencies.
- Present findings clearly to technical and non-technical stakeholders.

### Requirements

- 2+ years of experience in data analytics, business intelligence, or a related role.
- Strong SQL skills.
- Proficiency in Power BI.
- Good working knowledge of Excel.
- Ability to interpret data and communicate findings clearly.
- Strong analytical and problem-solving skills.
- Diploma or Degree in Data Analytics, Computer Science, Statistics, Business Analytics, or a related discipline.

### Preferred

- Experience with Python or pandas.
- Exposure to cloud data platforms such as AWS or Azure.
- Experience working with retail or e-commerce data.
""",

    "JOB-TEST-004_CYBERSECURITY_raw.txt": """
Cybersecurity Analyst

Sentinel Cyber Defence Pte. Ltd.

Location: Singapore
Employment type: Full time
Salary: Salary undisclosed
Posted: 4d ago

This is an on-site position.

### Key Responsibilities

- Monitor security alerts and investigate suspicious activity.
- Perform initial triage of cybersecurity incidents.
- Analyse logs from SIEM, endpoint, firewall, and network security platforms.
- Support vulnerability management activities.
- Assist with incident response and post-incident documentation.
- Maintain security procedures and operational documentation.
- Work with infrastructure and application teams on remediation activities.

### Candidate Requirements

- 2–4 years of experience in cybersecurity operations, SOC, incident response, or security monitoring.
- Hands-on experience with SIEM platforms.
- Understanding of network security, firewalls, endpoint protection, and common attack techniques.
- Familiarity with vulnerability management processes.
- Strong analytical and troubleshooting skills.
- Able to communicate clearly during security incidents.

### Qualifications

- Diploma or Degree in Cybersecurity, Information Technology, Computer Science, or related field.

### Advantageous

- Security+, CEH, or equivalent cybersecurity certification.
- Experience with Microsoft Sentinel.
- Knowledge of MITRE ATT&CK.
""",

    "JOB-TEST-005_IT_SUPPORT_raw.txt": """
IT Support Engineer

BrightPath Services Pte. Ltd.

Location: Jurong East, Singapore
Employment type: Full time
Salary: S$3,200 - S$4,200 per month
Posted: 5d ago

The role is primarily on-site.

### Responsibilities

- Provide Level 1 and Level 2 support for end users.
- Troubleshoot Windows laptops, desktops, printers, and mobile devices.
- Support Microsoft 365 applications and user accounts.
- Perform Active Directory account administration.
- Install approved software and hardware.
- Track incidents and service requests using the IT service desk system.
- Escalate complex issues to infrastructure or application support teams.
- Maintain IT asset and support documentation.

### Requirements

- 1–3 years of IT support, desktop support, or service desk experience.
- Good knowledge of Windows 10/11.
- Experience supporting Microsoft 365.
- Familiarity with Active Directory.
- Basic understanding of TCP/IP and networking.
- Strong customer-service and troubleshooting skills.
- Able to communicate clearly with non-technical users.

### Education

- Diploma in Information Technology, Computer Engineering, or related discipline.

### Nice to Have

- ITIL Foundation certification.
- Experience with Intune or endpoint-management tools.
""",

    "JOB-TEST-006_DIGITAL_MARKETING_raw.txt": """
Digital Marketing Executive

Momentum Digital Pte. Ltd.

Location: Singapore
Employment type: Full time
Salary: S$3,500 - S$4,500 per month
Posted: 2d ago

Hybrid working arrangement available after probation.

### What You Will Do

- Plan and execute digital marketing campaigns across paid search and social media channels.
- Manage Google Ads and Meta Ads campaigns.
- Monitor campaign performance and recommend optimisations.
- Use Google Analytics and reporting dashboards to analyse traffic and conversions.
- Support SEO activities including keyword research and content optimisation.
- Coordinate with designers, content writers, and account managers.
- Prepare monthly campaign performance reports for clients.

### What We Are Looking For

- 1–2 years of experience in digital marketing or performance marketing.
- Hands-on experience with Google Ads and Meta Ads.
- Familiarity with Google Analytics.
- Basic understanding of SEO.
- Strong written and verbal communication skills.
- Comfortable working with campaign data and performance metrics.

### Preferred

- Google Ads certification.
- Experience with Google Tag Manager.
- Familiarity with marketing automation or CRM platforms.
- Agency experience is an advantage.

### Education

Diploma or Degree in Marketing, Business, Communications, or a related field.
""",

    "JOB-TEST-007_PROJECT_COORDINATOR_raw.txt": """
Digital Project Coordinator

Orbit Solutions Asia Pte. Ltd.

Location: Paya Lebar, Singapore
Employment type: Full time
Salary: Salary undisclosed
Posted: 6d ago

Flexible work arrangement depending on project requirements.

### Role Responsibilities

- Coordinate timelines, meetings, action items, and project documentation.
- Track project milestones and follow up with internal stakeholders.
- Maintain project status reports and risk or issue logs.
- Support requirements-gathering workshops.
- Coordinate between business users, designers, developers, and vendors.
- Prepare meeting minutes and project presentation materials.
- Assist project managers with delivery administration.

### Requirements

- 2+ years of experience in project coordination, project administration, or similar work.
- Strong organisational and documentation skills.
- Good written and verbal communication skills.
- Comfortable coordinating across multiple teams.
- Proficiency with Microsoft Office or Microsoft 365.
- Able to manage multiple priorities and deadlines.

### Qualification

Diploma or Degree in Business, Information Technology, Project Management, or related discipline.

### Desirable

- Exposure to software-development or digital-transformation projects.
- Familiarity with Agile or Scrum environments.
- Experience using Jira or similar project-management tools.
""",

    "JOB-TEST-008_DEVOPS_raw.txt": """
Cloud DevOps Engineer

Nimbus Platform Engineering Pte. Ltd.

Location: Singapore
Employment type: Full time
Salary: S$6,000 - S$8,500 per month
Posted: 1d ago

This role follows a hybrid work model.

### Responsibilities

- Build and maintain CI/CD pipelines.
- Manage cloud infrastructure on AWS.
- Develop Infrastructure-as-Code using Terraform.
- Deploy and operate containerised workloads using Docker and Kubernetes.
- Monitor platform availability, performance, and reliability.
- Automate operational tasks using scripting.
- Support development teams with deployment and environment issues.
- Participate in incident troubleshooting and root-cause analysis.

### Required Experience and Skills

- 3+ years of experience in DevOps, cloud engineering, platform engineering, or related work.
- Hands-on AWS experience.
- Strong experience with CI/CD pipelines.
- Experience with Terraform.
- Experience with Docker and Kubernetes.
- Familiarity with Linux administration.
- Scripting experience using Python, Bash, or similar languages.
- Understanding of networking and cloud-security fundamentals.

### Preferred

- AWS Solutions Architect, AWS SysOps, or similar AWS certification.
- Experience with GitHub Actions or GitLab CI.
- Experience with monitoring tools such as Prometheus and Grafana.

### Education

Degree in Computer Science, Information Technology, Engineering, or related discipline preferred.
""",

    "JOB-TEST-009_CONTRACT_OPERATIONS_raw.txt": """
Application Operations Support Analyst

HarbourTech Systems Pte. Ltd.

Location: Singapore
Employment type: 12-month contract
Salary: S$4,000 - S$5,200 per month
Posted: 3d ago

This position is on-site and supports a 24x7 production environment.

### Responsibilities

- Monitor production applications and scheduled jobs.
- Investigate application alerts and service incidents.
- Perform first-level troubleshooting and incident escalation.
- Coordinate with application-development and infrastructure teams during outages.
- Execute approved operational procedures and recovery steps.
- Maintain incident records and operational documentation.
- Participate in service-restoration and post-incident activities.

### Requirements

- 2+ years of experience in application support, production support, or IT operations.
- Experience supporting enterprise applications in production environments.
- Basic SQL knowledge.
- Familiarity with Linux or Unix command-line environments.
- Understanding of incident-management processes.
- Strong troubleshooting and communication skills.

### Additional Requirements

- Must be willing to work rotating shifts, including nights, weekends, and public holidays.
- Must be eligible to work in Singapore without employer-sponsored work authorisation.
- Participation in an on-call roster is required.

### Preferred

- ITIL certification.
- Experience in financial-services technology environments.
""",

    "JOB-TEST-010_MESSY_LISTING_raw.txt": """
Systems & Automation Specialist

Vertex Operations Lab

Location: Singapore
Employment type: Contract
Salary: Up to S$5,500 monthly
Posted: Today

Small operations team seeking someone practical who can automate repetitive work,
support internal systems and help improve day-to-day technical processes.

Work from home some days, office presence required when needed.

You should be comfortable with Python scripting, REST APIs, Excel and basic SQL.
You will automate recurring reports, connect internal tools, investigate data issues,
document workflows, assist users when internal applications fail and work with vendors
when fixes are required.

At least 2 years of relevant IT, systems, automation or technical operations experience.

Need someone who can work independently, explain technical issues clearly and learn
unfamiliar tools quickly.

Diploma or degree in IT, computing or engineering preferred, but equivalent practical
experience will also be considered.

Nice if you know PowerShell, Power Automate, Git or cloud services.

Microsoft Power Platform certification would be useful but is not mandatory.

Occasional after-hours support may be required during system changes.
""",
}


def main() -> None:
    TEST_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Creating benchmark input files...")
    print()

    for filename, content in TEST_CASES.items():
        file_path = TEST_DATA_DIR / filename

        file_path.write_text(
            content.strip() + "\n",
            encoding="utf-8",
        )

        print(f"Created: {filename}")

    print()
    print(
        f"Created {len(TEST_CASES)} benchmark input files."
    )


if __name__ == "__main__":
    main()