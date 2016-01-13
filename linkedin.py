# -*- coding: utf-8 -*-

"""

@author: idwaker

This uses webdriver
"""

import sys
import csv
import time
import click
import getpass
import keyring
from selenium import webdriver
from selenium.common.exceptions import (WebDriverException,
                                        NoSuchElementException)


LINKEDIN_URL = 'https://www.linkedin.com'


class UnknownUserException(Exception):
    pass


class UnknownBrowserException(Exception):
    pass


class WebBus:
    """
    context manager to handle webdriver part
    """

    def __init__(self, browser):
        self.browser = browser
        self.driver = None

    def __enter__(self):
        # XXX: This is not so elegant
        # should be written in better way
        if self.browser.lower() == 'firefox':
            self.driver = webdriver.Firefox()
        elif self.browser.lower() == 'chrome':
            self.driver = webdriver.Chrome()
        elif self.browser.lower() == 'phantomjs':
            self.driver = webdriver.PhantomJS()
        else:
            raise UnknownBrowserException("Unknown Browser")

        return self

    def __exit__(self, _type, value, traceback):
        if _type is FileNotFoundError or _type is WebDriverException:
            click.echo("Please make sure you have this browser")
            return False
        if _type is UnknownBrowserException:
            click.echo("Please use either Firefox, PhantomJS or Chrome")
            return False

        self.driver.close()


def get_password(username):
    """
    get password from stored keychain service
    """
    password = keyring.get_password('linkedinpy', username)
    if not password:
        raise UnknownUserException("""You need to store password for this user
                                        first.""")

    return password


def login_into_linkedin(driver, username):
    """
    Just login to linkedin if it is not already loggedin
    """
    userfield = driver.find_element_by_id('login-email')
    passfield = driver.find_element_by_id('login-password')

    submit_xpath = '//form[@class="login-form"]/input[@name="submit"]'

    password = get_password(username)

    # If we have login page we get these fields
    # I know it's a hack but it works
    if userfield and passfield:
        userfield.send_keys(username)
        passfield.send_keys(password)
        submit = driver.find_element_by_xpath(submit_xpath)
        submit.click()


def collect_names(filepath):
    """
    collect names from the file given
    """
    names = []
    with open(filepath, 'r') as _file:
        names = [line.strip() for line in _file.readlines()]
    return names


@click.group()
def cli():
    """
    First store password

    $ python linkedin store username@example.com
    Password: **

    Then crawl linkedin for users

    $ python linkedin crawl username@example.com with_names output.csv --browser=firefox
    """
    pass


@click.command()
@click.option('--browser', default='phantomjs', help='Browser to run with')
@click.argument('username')
@click.argument('infile')
@click.argument('outfile')
def crawl(browser, username, infile, outfile):
    """
    Run this crawler with specified username
    """

    # first check and read the input file
    all_names = collect_names(infile)

    fieldnames = ['fullname', 'current summary', 'past summary', 'education',
                  ]
    # then check we can write the output file
    # we don't want to complete process and show error about not
    # able to write outputs
    with open(outfile, 'w') as csvfile:
        # just write headers now
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

    search_btn = '//form[@id="global-search"]//button[@class="search-button"]'
    link_title = './/a[@class="title main-headline"]'

    # now open the browser
    with WebBus(browser) as bus:
        bus.driver.get(LINKEDIN_URL)

        login_into_linkedin(bus.driver, username)

        for name in all_names:
            search_input = bus.driver.find_element_by_id('main-search-box')
            search_input.send_keys(name)

            search_button = bus.driver.find_element_by_xpath(search_btn)
            search_button.click()

            profiles = []

            # collect all the profile links
            results = bus.driver.find_element_by_id('results-container')
            links = results.find_elements_by_xpath(link_title)

            # get all the links before going through each page
            links = [link.get_attribute('href') for link in links]
            for link in links:
                # XXX: This whole section should be separated from this method
                bus.driver.get(link)

                overview = None
                overview_xpath = '//div[@class="profile-overview-content"]'
                try:
                    overview = bus.driver.find_element_by_xpath(overview_xpath)
                except NoSuchElementException:
                    click.echo("No overview section skipping this user")
                    continue

                # every xpath below here are relative
                fullname = None
                fullname_xpath = './/span[@class="full-name"]'
                try:
                    fullname = overview.find_element_by_xpath(fullname_xpath)
                except NoSuchElementException:
                    # we store empty fullname : notsure for this
                    fullname = ''
                else:
                    fullname = fullname.text.strip()

                current_summary = None
                csummary_xpath = './/tr[@id="overview-summary-current"]/td'
                try:
                    current_summary = overview.find_element_by_xpath(csummary_xpath)
                except NoSuchElementException:
                    current_summary = ''
                else:
                    current_summary = current_summary.text.strip()

                past_summary = None
                psummary_xpath = './/tr[@id="overview-summary-past"]/td'
                try:
                    past_summary = overview.find_element_by_xpath(psummary_xpath)
                except NoSuchElementException:
                    past_summary = ''
                else:
                    past_summary = past_summary.text.strip()

                education = None
                education_xpath = './/tr[@id="overview-summary-education"]/td'
                try:
                    education = overview.find_element_by_xpath(education_xpath)
                except NoSuchElementException:
                    education = ''
                else:
                    education = education.text.strip()

                data = {
                    'fullname': fullname,
                    'current summary': current_summary,
                    'past summary': past_summary,
                    'education': education,
                }
                profiles.append(data)

            with open(outfile, 'a+') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writerows(profiles)


@click.command()
@click.argument('username')
def store(username):
    """
    Store given password for this username to keystore
    """
    passwd = getpass.getpass()
    keyring.set_password('linkedinpy', username, passwd)
    click.echo("Password updated successfully")


cli.add_command(crawl)
cli.add_command(store)


if __name__ == '__main__':
    cli()
