# pylint: disable=no-name-in-module
"""
Contains tests for validating my blog
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


class BlogPostTester:
    blog_post: BlogPost
    page_content: str

    def find_keywords(self):
        patterns_not_found: List[str]
        for pattern in self.blog_post.keyword_patterns:
            match_found = re.search(pattern, self.page_content)
            if not match_found:
                patterns_not_found.append(pattern)
        return patterns_not_found


def verify_blog_post(blog_post: BlogPost, web_driver: WebDriver):
    web_driver.get(blog_post.url)
    pages_found: List[Page] = []
    pages_not_found: List[Page] = []
    for page in blog_post.pages:
        link = web_driver.find_element(By.LINK_TEXT, value=page.link_text_pattern)
        if not link:
            pages_not_found[page]
        else:
            page.link = link
            pages_found.append(page)

    keyword_pattern_not_found: List[str] = []
    for page in pages_found:
        # click() might not work. See https://stackoverflow.com/a/52405269
        web_driver.execute_script("arguments[0].click();", page.link)
        page_text = web_driver.find_element(By.XPATH, value="/html/body").text
        for keyword_pattern in page.keyword_patterns:
            match_found = re.search(keyword_pattern, page_text)
            if not match_found:
                keyword_pattern_not_found.append(keyword_pattern)

        if pages_not_found or keyword_pattern_not_found:
            raise Exception("Some elements could not be found")


class RetroBlogTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.blog_posts = [BlogPost]
        current_path = pathlib.Path(__file__).parent.resolve()
        with open(f"{current_path}/../test_data.json") as test_data_file:
            blog_post_test_data_list = json.load(test_data_file)
            for blog_post_data in blog_post_test_data_list:
                blog_post = BlogPost(**blog_post_data)
                cls.blog_posts.append(blog_post)
        # Remove model metaclass added by pydantic
        cls.blog_posts.pop(0)

        options = Options()
        options.add_argument("--headless")
        current_path = pathlib.Path(__file__).parent.resolve()
        service = Service(executable_path=f"{current_path}/../bin/chromedriver")
        cls.driver = webdriver.Chrome(options=options, service=service)

    def testTestData(self):
        blog_posts: List[BlogPost] = RetroBlogTest.blog_posts
        assert blog_posts
        assert len(blog_posts) == 1
        assert blog_posts[0].url == "https://tom1299.github.io/retro-blog/post/k8s-hardly-readable-configmap/"
        assert blog_posts[0].pages[0].link_text_pattern == "kubectl edit command"

    def testTestLinks(self):
        for blog_post in RetroBlogTest.blog_posts:
            verify_blog_post(blog_post, RetroBlogTest.driver)

    @classmethod
    def tearDownClass(cls):
        cls.driver.close()
