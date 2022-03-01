# pylint: disable=no-name-in-module
"""
Contains tests for validating the retro blog
"""
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


class Page(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    link_text_pattern: str
    keyword_patterns: List[str]
    link: WebElement = None


class BlogPost(BaseModel):
    url: str
    pages: List[Page]


class BlogPostTestResult:

    def __init__(self, url: str):
        self.url = url
        self.pages_not_found: List[Page] = []
        self.keywords_not_found: {str, List[str]} = {}

    def has_errors(self):
        return self.pages_not_found or self.keywords_not_found

    def get_errors(self) -> List[str]:
        if not self.has_errors():
            return None

        errors: List[str] = []
        for page_not_found in self.pages_not_found:
            errors.append(f"Linked page for keyword \"{page_not_found.link_text_pattern}\" not found ")
        for link, keyword_not_found in self.keywords_not_found:
            errors.append(f"Keywords \"{keyword_not_found}\" not found on page linked with text \"{link}\"")

        return errors

    def add_not_found(self, page: Page) -> None:
        self.pages_not_found.append(page)

    def add_keyword_not_found(self, keyword: str, page: Page) -> None:
        keywords_not_found = []
        if page.link_text_pattern in self.keywords_not_found:
            keywords_not_found = self.keywords_not_found[page.link_text_pattern]
        keywords_not_found.append(keyword)
        self.keywords_not_found = keywords_not_found


class BlogPostTester:

    def __init__(self, blog_post: BlogPost, web_driver: WebDriver):
        self.blog_post = blog_post
        self.blog_post_test_result: BlogPostTestResult = BlogPostTestResult(blog_post.url)
        self.web_driver = web_driver
        self.pages_found: List[Page] = []

    def verify_blog_post(self) -> BlogPostTestResult:
        for page in self.blog_post.pages:
            self.verify_page(page)

        return self.blog_post_test_result

    def get_link(self, page: Page) -> WebElement:
        link: WebElement = None

        print(f"Searching for href with text {page.link_text_pattern}")

        try:
            link = self.web_driver.find_element(By.LINK_TEXT, value=page.link_text_pattern)
        except NoSuchElementException:
            # Fallback if can not be found directly
            all_links: List[WebElement] = self.web_driver.find_element(By.XPATH, "//a[@href]")
            for alink in all_links:
                if re.search(page.link_text_pattern, alink.text):
                    link = alink
        return link

    def verify_page(self, page):
        self.web_driver.get(self.blog_post.url)
        link = self.get_link(page)
        if not link:
            self.blog_post_test_result.add_not_found(page)
            return

        # click() might not work. See https://stackoverflow.com/a/52405269
        self.web_driver.execute_script("arguments[0].click();", link)
        page_text = self.web_driver.find_element(By.XPATH, value="/html/body").text
        for keyword_pattern in page.keyword_patterns:
            self.verify_keyword(keyword_pattern, page, page_text)

    def verify_keyword(self, keyword_pattern, page, page_text):
        match_found = re.search(keyword_pattern, page_text)
        if not match_found:
            self.blog_post_test_result.add_keyword_not_found(keyword_pattern, page)


class RetroBlogTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.load_blogs()
        cls.create_web_driver()

    @classmethod
    def create_web_driver(cls):
        options = Options()
        options.add_argument("--headless")
        current_path = pathlib.Path(__file__).parent.resolve()
        service = Service(executable_path=f"{current_path}/../bin/chromedriver")
        cls.driver = webdriver.Chrome(options=options, service=service)

    @classmethod
    def load_blogs(cls):
        test_data_file_name = "test_data.json"
        cls.blog_posts = cls.load_test_data(test_data_file_name)

    @classmethod
    def load_test_data(cls, test_data_file_name):
        blog_posts: List[BlogPost] = []
        current_path = pathlib.Path(__file__).parent.resolve()
        with open(f"{current_path}/../{test_data_file_name}") as test_data_file:
            blog_post_test_data_list = json.load(test_data_file)
            for blog_post_data in blog_post_test_data_list:
                blog_post = BlogPost(**blog_post_data)
                blog_posts.append(blog_post)
        return blog_posts

    def testTestData(self):
        blog_posts: List[BlogPost] = RetroBlogTest.blog_posts
        assert blog_posts
        assert len(blog_posts) == 2
        assert blog_posts[0].url == "https://tom1299.github.io/retro-blog/post/k8s-hardly-readable-configmap/"
        assert blog_posts[0].pages[0].link_text_pattern == "kubectl edit command"

    def testLinks(self):
        for blog_post in RetroBlogTest.blog_posts:
            blog_post_tester = BlogPostTester(blog_post, RetroBlogTest.driver)
            test_result = blog_post_tester.verify_blog_post()
            assert not test_result.has_errors()

    @classmethod
    def tearDownClass(cls):
        cls.driver.close()
