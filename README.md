# webXray -- Risk Report Extension



Modified files:
- run_webxray.py
- webxray/Analyzer.py
- webxray/Reporter.py
- webxray/Utilities.py

Added files:
- resources/page_lists/demo_sites.txt
- webxray/recommendations.csv
- webxray/template.html
- webxray/use_risk.csv



What the project does
Why the project is useful
How users can get started with the project
Where users can get help with your project
Who maintains and contributes to the project

What was your motivation?
Why did you build this project?
What problem does it solve?
What did you learn?
What makes your project stand out?
If your project has a lot of features, consider adding a "Features" section and listing them here.

2. Project Description
2. Project Description
4. How to Install and Run the Project
5. How to Use the Project
6. Include Credits




webXray is a tool for analyzing webpage traffic and content, extracting legal policies, and identifying the companies which collect user data.  A command line user interface makes webXray easy for non-programmers to use, and those with advanced needs may analyze billions of requests by fully leveraging webXray's distributed architecture.  webXray has been used to run hundreds of concurrent browser sessions distributed across multiple continents.

webXray performs scans of single pages, random crawls within websites, and supports following pre-scripted sequences of page loads.  Unlike tools which rely on browsers with negligible user bases, webXray uses the consumer version of Chrome, the most popular browser in the world.  This means webXray is the best tool for producing scans which accurately reflect the experiences of most desktop web users.

webXray performs both "haystack" scans which give insights into large volumes of network traffic, cookies, local storage, and websockets, as well as "forensic" scans which preserve all file contents for use in reverse-engineering scripts, extracting advertising content, and verifying page execution in a forensically sound way.  An additional module of webXray, policyXray, finds and extracts the text of privacy policies, terms of service, and other related documents in several languages.  

Small sets of pages may be stored in self-contained SQLite databases and large datasets can be stored in Postgres databases which come pre-configured for optimum indexing and data retrieval.  In both cases, webXray produces several preconfigured reports which are rendered as CSV files for easy importing into programs such as Excel, R, and Gephi.  Users proficient in SQL may use advanced queries to perform their own analyses with ease.

webXray uses a custom library of domain ownership to chart the flow of data from a given third-party domain to a corporate owner, and if applicable, to parent companies.  Domain ownership is further enhanced with classifications of what domains are used for (e.g. 'marketing', 'fonts', 'hosting'), links to several types of policies in numerous languages, as well as links to homepages, and lists of medical terms used by specific advertisers.

More information and detailed installation instructions may be found on the [project website](http://webXray.org).

# Basic Installation (from https://github.com/timlib/webXray.git)

webXray requires Python 3.4+ and Google Chrome to function, pip3 for dependency installation, and Readability.js for text extraction.  These may be installed in the following steps:

1) Install the latest version of Python3 along with pip3, there are various guides online to doing this for your OS of choice.

2) Install Google Chrome.  For desktop systems (e.g. Mac, Windows, Linux) you can get Chrome from Google's website.  When running in headless linux environments, installing from the official .deb file is recommended.

3)  Clone this repository from GitHub:

        git clone https://github.com/timlib/webxray.git

4) To install Python dependencies (websocket-client, textstat, lxml, and psycopg2), run the following command:

        pip3 install -r requirements.txt

5) If you want to extract page text (eg policies), you must download the file Readability.js from [this address](https://raw.githubusercontent.com/mozilla/readability/master/Readability.js) and copy it into the directory "webxray/resources/policyxray/".  You can also do this via the  command line as follows:
    
        cd webxray/resources/policyxray/
        wget https://raw.githubusercontent.com/mozilla/readability/master/Readability.js

# Using webXray

To start webXray in interactive mode type:

    python3 run_webxray.py

The prompts will guide you to scanning a sample list of websites using the default settings of Chrome in windowed mode and a SQLite database.  If you wish to run several browsers in parallel to increase speed, leverage a more powerful database engine, or perform other advanced tasks, please see the [project website](http://webXray.org/#advanced_options) for details.

To see how to control webXray via command-line flags, type the following:

    python3 run_webxray.py -h

# Using webXray to Analyze Your Own List of Pages

The raison d'être of webXray is to allow you to analyze pages of your choosing.  In order to do so, first place all of the page addresses 
you wish to scan into a text file and place this file in the "./resources/page_lists" directory.  Make sure your addresses start with 
"http://" or 
"https://", if not, webXray will not recognize them as valid addresses.  Once you have placed your page list in the 
"./resources/page_lists/" 
directory you may run webXray and it will allow you to select your page list.

# Viewing and Understanding Risk Reports

After completing "Collect Data" and "Risks and Recommendations", the risk summaries and assigned recommendations by page will be output to the '/resports/\<database\>/summaries' directory.

Each PDF will contain the following information:
- *URL*: The name of the page being summarized
- *Date*: The time the report was generated
- *Stoplight*: And image of a red/yellow/green stoplight representing the high/medium/low risk assignment for the page
- *Top 10 Third Party Cookies*: The site, usage categories, and number of cookies of the third party domains associated with the highest risk scores
- *Recommendation*: Recommendations based on the high/medium/low risk assignment for the page

# Credits

The original tool was produced by Timothy Libert, and can be found in the [webXray GitHub](https://github.com/timlib/webXray.git) or the [https://webxray.org/](https://webxray.org/).

The edits to the tool were created by Leah Restad, Curt Williams, and Harish Balaji from Carnegie Mellon University.