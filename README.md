# Diploma FinalYearProject
Final Year Project :- SmartIntern

The transition from academia to the professional workforce presents a significant
bottleneck for college students, who must simultaneously navigate career
advancement and secure financial aid. Traditional discovery platforms and job
portals are heavily fragmented and rely on static, keyword-based search
methodologies. These legacy systems lack semantic understanding, leading to
inefficient matching, and fail to accommodate the rigid demographic criteria
required for scholarship distribution. Furthermore, modern platforms attempting to
utilize machine learning frequently succumb to the "Cold Start" problem, where
algorithms fail due to a lack of initial user interaction data.
To address these systemic inefficiencies, this project introduces SmartIntern, an
intelligent, centralized recommendation ecosystem tailored for the collegiate
demographic. SmartIntern shifts the paradigm from manual searching to automated
discovery through a highly scalable, dual-engine architecture. The primary
recommendation engine utilizes Natural Language Processing (NLP)—specifically
Term Frequency-Inverse Document Frequency (TF-IDF) and Cosine Similarity—to
mathematically calculate the semantic alignment between unstructured student skill
sets and internship requirements. Concurrently, a secondary heuristic engine applies
rule-based Regular Expressions (Regex) to process complex demographic
constraints, ensuring 100% deterministic accuracy for financial aid and scholarship
eligibility.
Developed using a lightweight Python (Flask) backend and a serverless
PostgreSQL database (Supabase), the system ensures high concurrency and
stateless cloud scalability. Crucially, the platform actively mitigates the User Cold
Start vulnerability by enforcing a strict, middleware-driven profile gatekeeper,
guaranteeing the algorithmic matrices have baseline vector data prior to execution.
The resulting application successfully eliminates cognitive overload, providing
students with a unified, highly personalized dashboard that proactively delivers
precision-matched career and financial opportunities.


Team Members:

1.Ayush Parkhe - AP

2.Vaishnavi Patil - VP

3.Dipika Warade - DW

4.Prajakta Mane - PM

5.Dipali Sanap - DS

6.Dipali Khosare - DK




