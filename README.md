# webXray -- Risk Report Extension


Our tool extends an existing tool by Timothy Libert, called [webXray](https://webxray.org/).


According to WebXray documentation, the tool can be used for analyzing website traffic, identifying the sites that collect user data, and also can be used for extracting legal policies. Although it has some great features, there are a few shortcomings in terms of usability and practicality. It is not easy for ordinary, non-technical users to set it up, comprehend the results, and take subsequent actions from the results.


Our project focuses on reengineering some components in this tool and adding some functionality to make it more user-friendly.




# Changes for Risk Report Extension


Since our tool is based on [webXray](https://webxray.org/), we include the “Modified” and “Added” files below.


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


# Basic Installation (from [webXray GitHub](https://github.com/timlib/webXray.git))


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


# Using webXray for Risk Reports


To start webXray in interactive mode type:


   python3 run_webxray.py


Follow the prompts to first "Collect Data" then get "Risks and Recommendations" for a database of your choice. Both 'example_sites.txt' from the original tool and 'demo_sites.txt' from our edits are available for initial data collection.


# Viewing and Understanding Risk Reports


After completing "Collect Data" and "Risks and Recommendations", the risk summaries and assigned recommendations by page will be output to the '/reports/\<database\>/summaries' directory.


Each PDF will contain the following information:
- *URL*: The name of the page being summarized
- *Date*: The time the report was generated
- *Stoplight*: And image of a red/yellow/green stoplight representing the high/medium/low risk assignment for the page
- *Top 10 Third Party Cookies*: The site, usage categories, and number of cookies of the third party domains associated with the highest risk scores
- *Recommendation*: Recommendations based on the high/medium/low risk assignment for the page


# Credits


The original tool was produced by Timothy Libert, and can be found in the [webXray GitHub](https://github.com/timlib/webXray.git) or [https://webxray.org/](https://webxray.org/).


The edits to the tool were created by Leah Restad, Curt Williams, and Harish Balaji from Carnegie Mellon University. The Risks Report extension is not currently being maintained.

