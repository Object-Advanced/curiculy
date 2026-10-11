# Pennsylvania: requirement worksheet

**Draft for review (2026-10-11).** This is the first state pack. Nothing here is built. Statuses are judged against the planned design in the [Product spine](../product-spine.md), using the process in [State requirements](README.md). **Not legal advice.**

## Scope
- **Covered here:** Option 1, the **home education program**, 24 P.S. §13-1327.1 (Section 1327.1 of the Public School Code of 1949). This is the option most Pennsylvania homeschoolers use.
- **Not covered:** the other three options:
  - a certified private tutor
  - a satellite of a religious day school
  - a satellite of an accredited school
  
  Families using those follow their school's rules. That could become a custom pack later.

## Sources
- PA Department of Education, *Basic Education Circular: Home Education Program*, 24 P.S. §13-1327.1, issued **2023-08-21**: [pa.gov](https://www.pa.gov/agencies/education/resources/policies-acts-and-laws/basic-education-circulars-becs/purdons-statutes/home-education-program)
- HSLDA, [How to comply with Pennsylvania's homeschool law](https://hslda.org/post/how-to-comply-with-pennsylvanias-homeschool-law), and the [Pennsylvania page](https://hslda.org/legal/pennsylvania)
- **To confirm:** the statute's exact wording on [palegis.us](https://www.palegis.us) (Public School Code of 1949, Act 14, §1327.1). Rows marked *(to confirm)* rest on secondary sources only.

## Open questions for review
Each needs a decision before its rule is built.

| # | Question | Rows |
|---|---|---|
| Q1 | **Health records.** The affidavit must include evidence of immunization (or an exemption) and of required health and medical services. Should Curiculy store these documents at all? They're sensitive data about children. Or do we mark them "outside Curiculy" with a reminder? | 6, 7 |
| Q2 | **How much of the affidavit do we make?** Districts may use their own forms. Options: (a) only the **objectives outline**, generated from courses; (b) a filled-in copy of PDE's sample affidavit. Option (b) needs a birth date or age, the address and the phone number, none of which Curiculy stores today. | 3, 5 |
| Q3 | **Objectives by subject.** A list of courses and materials isn't really "education objectives". Should each course get a short objectives field (pre-filled from the curriculum's description and edited by the parent)? Or is a course list acceptable? | 5 |
| Q4 | **Subjects without their own curriculum:** safety education (including fire prevention), health, physical education, music, art, civics. How does a family show these? A light activity log, tagging a lesson as covering a second subject, or "parent confirms"? | 11, 12 |
| Q5 | **Days or hours.** The family picks one. Hours need lesson minutes, which Curiculy doesn't track yet. Is an estimate from the guide (editable) acceptable? | 10 |
| Q6 | **The log "made at the time of instruction".** Curiculy records the date a lesson is checked off. Should the report show the date each entry was *logged*? Should lessons checked off long after their date be flagged? | 14 |
| Q7 | **How many work samples?** The law asks for samples but doesn't give a number; the evaluator decides. Should the pack ship with no number (the family enters their evaluator's expectation; until then it's "parent confirms"), or with a suggested default to check with evaluators (e.g. beginning, middle and end of year per subject)? | 15 |
| Q8 | **Standardized tests (grades 3, 5, 8).** Curiculy can't verify a test. Should the parent record the test's name from PDE's approved list, who gave it (not a parent), and the results, with an upload? Status would be "parent confirms" with that structure. | 16 |
| Q9 | **Grades 9–12:** graduation course minimums (and diplomas). In scope for launch? | 22 |
| Q10 | **Special education (IDEA):** separate provisions apply. In scope for launch? | 23 |
| Q11 | **Grade levels.** Rules depend on grade (tests in 3, 5 and 8; elementary vs secondary subjects and hours). Today a child's grade is free text. Should it become a fixed list? | 10–12, 16 |

## Requirements
**Option 1: home education program, 24 P.S. §13-1327.1**

### A. The supervisor
| # | Requirement | Source | Curiculy today | Status | Notes |
|---|---|---|---|---|---|
| 1 | The supervisor (parent, guardian or legal custodian) has a high school diploma or equivalent | PDE BEC; HSLDA | nothing | **Outside Curiculy** | Attested on the affidavit |

### B. Affidavit (or unsworn declaration)
| # | Requirement | Source | Curiculy today | Status | Notes |
|---|---|---|---|---|---|
| 2 | File with the superintendent of the district of residence **before starting**, then **by August 1** every year. Notarized affidavit or unsworn declaration. | PDE BEC; HSLDA | nothing | **Outside Curiculy** (filing); deadline as a **Task** | Curiculy reminds; the parent uploads a copy as proof ("parent confirms") |
| 3 | Names of supervisor and child, child's age, address, phone | HSLDA | child's name only; no birth date, address or phone | **Needs a decision** | Q2 |
| 4 | Assurance that subjects are taught in English | HSLDA | nothing | **Outside Curiculy** | Attested |
| 5 | **Outline of proposed education objectives by subject area** | PDE BEC; HSLDA | none (courses planned) | **Partly covered** | Courses give subject and materials; objectives need Q3 |
| 6 | Evidence of immunization, or a medical or religious/philosophical exemption | PDE BEC; HSLDA | nothing | **Needs a decision** | Q1 |
| 7 | Evidence of required health and medical services (Article XIV), or an exemption | PDE BEC; HSLDA | nothing | **Needs a decision** | Q1 |
| 8 | Certification of compliance with §1327.1 | HSLDA | nothing | **Outside Curiculy** | Attested |
| 9 | Certification that the supervisor, adults in the home and legal custodians have no specified criminal convictions in the past five years | HSLDA | nothing | **Outside Curiculy** | Attested |

### C. Instruction
| # | Requirement | Source | Curiculy today | Status | Notes |
|---|---|---|---|---|---|
| 10 | **180 days**, or **900 hours** (elementary) / **990 hours** (secondary) | HSLDA | attendance per child per day; no minutes | **Partly covered** | Days: attendance marked present. Hours: Q5. Elementary vs secondary: Q11. |
| 11 | **Elementary subjects:** English (spelling, reading, writing); arithmetic; science; geography; civics; history of the U.S. and Pennsylvania; health and physiology; physical education; music; art; safety education, including regular and continuous instruction in the dangers and prevention of fires | HSLDA | no real subjects ("Subject: Unfiled") | **Partly covered** | Courses' subjects checked against this list; subjects without a curriculum: Q4 |
| 12 | **Secondary subjects:** English (language, literature, speech, composition); mathematics (general math, algebra, geometry); science; geography; social studies (civics, world history, history of the U.S. and Pennsylvania); health; physical education; music; art; safety education, including fire prevention | HSLDA | as above | **Partly covered** | As row 11; Q4, Q9 |
| 13 | Instruction in English | HSLDA | nothing | **Outside Curiculy** | |

### D. Portfolio (kept by the family; reviewed by the evaluator, not sent to the district)
| # | Requirement | Source | Curiculy today | Status | Notes |
|---|---|---|---|---|---|
| 14 | A **log made at the time of instruction** that names, by title, the reading materials used | HSLDA; statute wording *(to confirm)* | completed lessons with completion dates (since Oct 2026); reading-list preset | **Partly covered** | Planned: completed lessons plus titles from both Library shelves. Q6. |
| 15 | **Samples** of writings, worksheets, workbooks or creative materials used or developed by the student | HSLDA; statute wording *(to confirm)* | work samples on lessons; inbox | **Partly covered** | Planned: samples per subject per term; how many is Q7 |
| 16 | **Grades 3, 5 and 8:** results in reading/language arts and math from the PSSA or a nationally normed test on PDE's approved list; not given by a parent | PDE BEC; HSLDA | nothing | **Needs a decision** | Q8. PDE's approved list: California Achievement Test, Comprehensive Testing Program (CTP IV), Iowa Test of Basic Skills, Measures of Academic Progress (MAP), Metropolitan Achievement Test, Peabody Individual Achievement Test (revised), Stanford Achievement Test, TerraNova, Woodcock-Johnson, Wechsler Individual Achievement Test (current versions). The district must let the child take the PSSA at school if the family asks. |
| 17 | The portfolio is kept for a period after the school year | *(to confirm the rule and the period)* | files kept indefinitely | **Needs a decision** | Confirm against the statute before relying on it |

### E. Annual evaluation
| # | Requirement | Source | Curiculy today | Status | Notes |
|---|---|---|---|---|---|
| 18 | A yearly evaluation by a **qualified evaluator**: a licensed psychologist; a PA-certified teacher with two years' experience; or a nonpublic teacher or administrator with two years' experience in the last ten. Others need the superintendent's prior consent. Not the supervisor or their spouse. | PDE BEC; HSLDA | nothing | **Outside Curiculy** | Store the evaluator's name and contact; "Book your evaluator" **Task** |
| 19 | The evaluator **interviews the child and reviews the portfolio** | HSLDA | portfolio presets and PDF | **Partly covered** | Curiculy makes the portfolio; the interview is outside Curiculy |
| 20 | Written **certification that an appropriate education is occurring**, submitted to the superintendent **by June 30** | PDE BEC; HSLDA | nothing | **Outside Curiculy** (submitting); deadline as a **Task** | The parent uploads the letter ("parent confirms"). Missing it can lead to a hearing, probation or losing the right to homeschool for up to a year (PDE BEC). |
| 21 | If concerns arise during the year, the superintendent may require an evaluation within 30 days | HSLDA | nothing | **Outside Curiculy** | A Task added by hand |

### F. Other
| # | Requirement | Source | Curiculy today | Status | Notes |
|---|---|---|---|---|---|
| 22 | **Graduation (grades 9–12):** 4 years of English, 3 of math, 3 of science, 3 of social studies, 2 of arts and humanities | §1327.1(d) as quoted on pa.gov; HSLDA | nothing (no credits or transcript) | **Needs a decision** | Q9 |
| 23 | **Special education (IDEA):** separate provisions, including evaluator rules | HSLDA (special needs article not yet read) | nothing | **Needs a decision** | Q10; read HSLDA's special-needs article and the statute first |
| 24 | Moving districts: request a letter of transfer by registered mail 30 days before moving, then file it with the new district | HSLDA | nothing | **Outside Curiculy** | A Task added by hand |

**Not requirements on the family:** the right to join district extracurricular, cocurricular, academic and CTE programs (PDE BEC); districts lending curriculum materials on request.

## What this means for the spine
These are needed whatever the answers above:
- **A state on the household.** Today only a placeholder exists.
- **A structured grade per child** (Q11) and probably a birth date (Q2).
- **Subjects** that map to Pennsylvania's elementary and secondary lists.
- **Attendance** in days, and **minutes** if hours mode is wanted (Q5).
- **Tasks** for August 1, the evaluator and June 30.
- **"Parent confirms" items with uploads,** for everything outside Curiculy.
