# pylint: disable=no-name-in-module
"""
Contains tests for validating the retro blog
"""
from __future__ import annotations
import re
import json
import pathlib
from typing import List
import unittest
from pydantic import BaseModel
from selenium.webdriver.remote.webdriver import WebDriver, WebElement
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium import webdriver
from typing import Optional


class Page(BaseModel):
    name: Optional[str]
    url: Optional[str]
    link_text_pattern: Optional[str]
    keyword_patterns: Optional[List[str]]
    pages: Optional[List[Page]]


class PageTestResult:

    def __init__(self, url: str):
        self.url = url
        self.pages_not_found: List[Page] = []
        self.keywords_not_found: {str, List[str]} = {}

    def has_errors(self):
        return self.pages_not_found or self.keywords_not_found

    def get_errors(self) -> List[str]:
        if not self.has_errors():
            return []

        errors: List[str] = []
        for page_not_found in self.pages_not_found:
            errors.append(f"Linked page for keyword \""
                          f"{page_not_found.link_text_pattern}\" not found ")
        for keyword_not_found in self.keywords_not_found:
            errors.append(f"Keywords \"{keyword_not_found}\" not found")

        return errors

    def add_not_found(self, page: Page) -> None:
        self.pages_not_found.append(page)

    def add_keyword_not_found(self, keyword: str, page: Page) -> None:
        keywords_not_found = []
        if page.link_text_pattern in self.keywords_not_found:
            keywords_not_found = self.keywords_not_found[page.link_text_pattern]
        keywords_not_found.append(keyword)
        self.keywords_not_found = keywords_not_found


class PageTester:

    def __init__(self, page: Page, web_driver: WebDriver):
        self.page = page
        self.page_test_result: PageTestResult = PageTestResult(page.url)
        self.web_driver = web_driver
        self.pages_found: List[Page] = []

    def verify_all_pages(self) -> List[PageTestResult]:
        self.verify_page(self.page)
        all_results = [self.page_test_result]
        if self.page.pages:
            for page in self.page.pages:
                if not page.url:
                    self.web_driver.get(self.page.url)
                    url = self.get_link_url(page)
                    page.url = url
                page_tester = PageTester(page, self.web_driver)
                all_results.extend(page_tester.verify_all_pages())
        return all_results

    def get_link_url(self, page: Page) -> str:
        link: WebElement = None

        print(f"Searching for href with text {page.link_text_pattern}")

        try:
            link = self.web_driver.find_element(By.LINK_TEXT, value=page.link_text_pattern)
        except NoSuchElementException:
            # Fallback if the link can not be found directly
            all_links: List[WebElement] = self.web_driver.find_elements(By.XPATH, "//a[@href]")
            for alink in all_links:
                if re.search(page.link_text_pattern, alink.text):
                    link = alink
                    break
                if re.search(page.link_text_pattern, alink.accessible_name):
                    link = alink
                    break

        return link.get_attribute('href')

    def verify_page(self, page):
        self.web_driver.get(self.page.url)
        page_text = self.web_driver.find_element(By.XPATH, value="/html/body").text
        if not page.keyword_patterns:
            return
        for keyword_pattern in page.keyword_patterns:
            self.verify_keyword(keyword_pattern, page, page_text)

    def verify_keyword(self, keyword_pattern, page, page_text):
        match_found = re.search(keyword_pattern, page_text)
        if not match_found:
            print(f"Did not find keyword '{keyword_pattern}' on {page.url}")
            self.page_test_result.add_keyword_not_found(keyword_pattern, page)


class PageTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.create_web_driver()

    @classmethod
    def create_web_driver(cls):
        options = Options()
        options.add_argument("--headless")
        current_path = pathlib.Path(__file__).parent.resolve()
        service = Service(executable_path=f"{current_path}/../bin/chromedriver")
        cls.driver = webdriver.Chrome(options=options, service=service)

    @classmethod
    def tearDownClass(cls):
        cls.driver.close()


def load_test_data():
    pages: List[Page] = []
    current_path = pathlib.Path(__file__).parent.resolve()
    with open(f"{current_path}/../test_data.json") as test_data_file:
        page_test_data_list = json.load(test_data_file)
        for page_data in page_test_data_list:
            pages.append(Page(**page_data))
    return pages


def add_test(cls, page: Page):
    def page_test_method(self):
        blog_post_tester = PageTester(page, PageTest.driver)
        test_results = blog_post_tester.verify_all_pages()
        at_least_one_error = False
        for result in test_results:
            if result.has_errors():
                print(f"Page {result.url} had errors: {result.get_errors()} ")
                at_least_one_error = True
            else:
                print(f"Page {result.url} had no errors")
        assert not at_least_one_error

    page_test_method.__name__ = f"test-{page.name}"
    setattr(cls, page_test_method.__name__, page_test_method)


for blog_post in load_test_data():
    add_test(PageTest, blog_post)
