# SmartVax
Intelligent Vaccination Tracking System with Proactive Dropout Prevention


# Introduction

SMART VAX is a web-based healthcare management system developed to simplify childhood vaccination tracking and improve immunization follow-up. The platform helps parents manage their children's vaccination schedules while providing healthcare workers with tools to monitor vaccination progress and identify children who may be at risk of missing scheduled doses.

The system combines web technologies, artificial intelligence and machine learning to provide a centralised platform for vaccination management.

## Key Features

- **Parent Dashboard:** Register children, manage profiles and monitor vaccination progress.
- **Digital Vaccination Records:** Maintain organised vaccination histories for each child.
- **Automated Vaccination Scheduling:** Generate personalised vaccination schedules based on the child's date of birth.
- **Smart Reminders:** Notify parents about upcoming and overdue vaccination doses through configured notification services.
- **AI Vaccine Assistant:** Answer common vaccination-related questions using Claude API integration.
- **Dropout Risk Prediction:** Apply machine learning techniques to estimate the risk of children missing future vaccination doses.
- **ASHA Worker Dashboard:** View assigned children, monitor overdue vaccinations and manage follow-up activities.
- **Admin Portal:** Manage users, monitor vaccination coverage and review dropout risk reports.

## Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| Backend | Flask |
| Frontend | HTML, CSS, JavaScript |
| Database | MySQL |
| Machine Learning | Scikit-learn |
| AI Integration | Claude API |
| Task Scheduling | APScheduler |
| API Communication | REST API, JSON |
| Email Notifications | SMTP |
| Development Environment | VS Code |

## Machine Learning

The system incorporates a machine learning module to estimate vaccination dropout risk based on vaccination history and related features.

Algorithms considered:
- Logistic Regression
- Random Forest
- Gradient Boosting / XGBoost

The prediction results are categorised into Low, Medium and High risk levels to help healthcare workers prioritise follow-up activities.

## System Modules

**1. Parent Module**
- Parent registration and login.
- Child profile management.
- Vaccination schedule and progress tracking.
- AI-powered vaccine assistance.

**2. ASHA Worker Module**
- Assigned-area monitoring.
- Overdue vaccination lists.
- Dropout risk monitoring.
- Follow-up visit management.

**3. Admin Module**
- User and worker management.
- Vaccination coverage monitoring.
- Administrative dashboard.
- Dropout prevention reports.

## Project Workflow

1. Parents create an account and register their children.
2. The system generates vaccination schedules using the child's date of birth.
3. Vaccination details are stored in the MySQL database.
4. The reminder service checks upcoming and overdue doses.
5. The machine learning module estimates vaccination dropout risk.
6. ASHA workers review high-risk cases and manage follow-ups.
7. Parents can access vaccination information through the AI Vaccine Assistant.

## Project Objectives

- Digitise traditional childhood vaccination records.
- Reduce missed and delayed vaccination appointments.
- Simplify vaccination schedule management.
- Improve communication between parents and healthcare workers.
- Support early identification of potential vaccination dropouts.
- Improve the organisation of vaccination follow-up activities.

## Future Scope

- Regional language support, including Hindi and Marathi.
- WhatsApp-based vaccination reminders.
- Dedicated Android and iOS applications.
- Integration with national immunization platforms.
- Explainable machine learning predictions.
- QR-based digital vaccination certificates.
- Geographic mapping for healthcare worker visits.

## Limitations

- The machine learning module primarily uses synthetic data and requires validation with real-world vaccination data.
- Vaccination records are not automatically verified against government databases.
- External notification services require separate configuration.
- AI-generated information should not replace professional medical advice.

## Installation and Setup

**Prerequisites**
- Python 3.x
- MySQL Server
- Git
- Visual Studio Code

**1. Clone the repository**

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
```

**2. Navigate to the project folder**

```bash
cd smart-vax
```

**3. Create a virtual environment**

```bash
python -m venv venv
```

**4. Activate the virtual environment (Windows PowerShell)**

```powershell
.\venv\Scripts\Activate.ps1
```

**5. Install dependencies**

```bash
pip install -r requirements.txt
```

**6. Configure environment variables**

Create a `.env` file using `.env.example` and enter your local MySQL credentials and required API configuration.

**7. Set up the MySQL database**

Import the provided SQL scripts using MySQL Workbench or the MySQL command-line client.

**8. Run the application**

```bash
python app.py
```

Open your browser and visit:

```text
http://127.0.0.1:5000
```

## Project Information

- **Project Name:** SMART VAX – Intelligent Vaccination Tracking System
- **Project Domain:** Healthcare Technology, Artificial Intelligence and Machine Learning
- **Project Type:** Full-Stack Web Application
- **Academic Year:** 2026–2027
- **Institution:** Bharati Vidyapeeth (Deemed to be University), Department of Engineering and Technology, Navi Mumbai


## Author

**Mohd Abrar Mammoo**

---

SMART VAX aims to make childhood vaccination management more organised and accessible through digital records, automated reminders and intelligent follow-up support.
