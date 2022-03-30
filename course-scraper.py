import os
from bs4 import BeautifulSoup
import csv
import re
import requests
import time
import sys


def notify(prefix="Finished in ", suffix=" seconds."):
    def inner_timer(func):
        def wrapper(*args, **kwargs):
            print(f"{prefix}", end="", flush=True)
            start_time = time.time()
            ret = func(*args, **kwargs)
            print(f"{suffix} ({(time.time() - start_time):.1f}s)")
            return ret

        return wrapper

    return inner_timer


@notify(prefix="Downloading courses to 'courses.html'...", suffix=" done.")
def download_courses(url):
    r = requests.get(url)
    soup = BeautifulSoup(r.content, "lxml")
    with open("courses.html", "w", encoding="utf-8") as f:
        f.write(soup.prettify())


def find_field_of_study_mappings(soup):
    result = {}
    for field_of_study in soup.find("select", class_="field-of-study-filter").find_all("option"):
        result[field_of_study["value"]] = field_of_study.text.strip()
    result[""] = ""
    return result


@notify(prefix="Parsing 'courses.html'...", suffix=" done.")
def parse_courses(soup, field_of_study_mapping):
    term_pattern = re.compile(r" \d\d? ")  # Matches either a single or two digits with whitespace on either side

    courses = {}

    program = soup.find("div", class_="programplan")
        
    for term in program.find_all("section"):
        
        current_term = term_pattern.search(term.header.h3.text.strip()).group(0).strip()
        
        for specialisation in term.find_all("div", class_="specialization"):
            
            spec_text = specialisation.caption.span
            current_specialisation = ' '.join(spec_text.text.split()[1:]) if spec_text else ''
                        
            for current_period, period in enumerate(specialisation.find_all("tbody", class_="period"), start=1):
                
                for course in period.find_all("tr", class_="main-row"):
                    
                    fields_of_study = list(
                        map(lambda x: field_of_study_mapping[x], course["data-field-of-study"].split("|"))
                    )
                    
                    code, name, hp, level, block, type_, _ = map(lambda x: x.text.strip(), course.find_all("td"))
                    
                    if not code in courses:
                        courses[code] = []

                    if not tuple(
                        [current_term, current_period, tuple(block.split("/") if "/" in block else block)]
                    ) in list(
                        map(
                            lambda course: tuple([course["Termin"], course["Period"], tuple(course["Block"])]),
                            courses[code],
                        )
                    ):
                        courses[code].append(
                            {
                                "Kurskod": code,
                                "Namn": f'=HYPERLINK("https://liu.se/studieinfo/kurs/{code.lower()}", "{name}")',
                                "Hp": int(hp.replace("*", "")) / (hp.count("*") + 1),
                                "Nivå": level,
                                "Block": block.split("/") if "/" in block else [block],
                                "O/V/F": type_.split("/") if "/" in type_ else [type_],
                                "Termin": current_term,
                                "Period": current_period,
                                "Perioder": hp.count("*") + 1,
                                "Inriktning": list([current_specialisation]),
                                "Område": fields_of_study,
                            }
                        )

                    if current_specialisation != "":
                        for course_variant in courses[code]:
                            if course_variant["Inriktning"] == list([""]):
                                course_variant["Inriktning"] = list([current_specialisation])
                            elif not current_specialisation in course_variant["Inriktning"]:
                                course_variant["Inriktning"].extend(list([current_specialisation]))
                                    
    return courses


@notify(prefix="Writing output to 'courses.csv'...", suffix=" done.")
def write_output(courses):
    with open("courses.csv", "w", encoding="UTF-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "Kurskod",
                "Namn",
                "Hp",
                "Nivå",
                "Block",
                "O/V/F",
                "Termin",
                "Period",
                "Perioder",
                "Inriktning",
                "Område",
            ],
            delimiter="\t",
        )
        writer.writeheader()
        for course in courses.values():
            for course_variant in course:
                writer.writerow({k: ",".join(v) if isinstance(v, list) else v for k, v in course_variant.items()})


if __name__ == "__main__":
    url = sys.argv[1]

    if not os.path.isfile("courses.html"):
        download_courses(url)
    else:
        print("Found 'courses.html', skipping download.")

    with open("courses.html", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "lxml")

    field_of_study_mapping = find_field_of_study_mappings(soup)
    courses = parse_courses(soup, field_of_study_mapping)
    write_output(courses)