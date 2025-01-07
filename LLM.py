import json
import glob
import os
from openai import OpenAI

def get_table_clusters(folder_path='prospr/*.json'):
    """
    Scans the specified folder for JSON files
    and extracts table structures from each file.
    Returns a dict of file_name -> [list of table info].
    """
    file_structure = {}
    json_files = glob.glob(folder_path)

    for json_file in json_files:
        file_name = os.path.basename(json_file)
        with open(json_file, 'r') as file:
            data = json.load(file)

        file_structure[file_name] = []
        if isinstance(data, list):
            for table in data:
                if 'table_name' in table:
                    table_info = {
                        'table_name': table['table_name'],
                        'table_description': table.get('table_description', ''),
                        'columns': table.get('columns', [])
                    }
                    file_structure[file_name].append(table_info)
    return file_structure

def create_openai_client(api_key):
    """
    Creates and returns an OpenAI client with the provided API key.
    """
    return OpenAI(api_key=api_key)

def get_relevant_files(client, file_names, prompt):
    """
    Uses the OpenAI client to determine which files
    are relevant to the user's query. Returns a list
    of relevant file names.
    """
    system_prompt = """You are a database expert that helps identify relevant database files.
                        You must return your response as a valid JSON object with the following structure:
                        {
                            "relevant_files": ["file1.json", "file2.json"]
                        }
                        Only include files that are directly relevant to the user's query."""

    user_prompt = f"""Given the following user query: "{prompt}"
                        Which of these database files are relevant?
                        Available files: {file_names}
                        Return only the relevant files in the specified JSON format."""

    print("---- get_relevant_files Prompt ----")
    print(system_prompt + "\n\n" + user_prompt)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": system_prompt + "\n\n" + user_prompt}]
    )
    response_text = response.choices[0].message.content

    # Clean up the response text
    response_text = response_text.replace('```json', '').replace('```', '').strip()
    print("---- get_relevant_files Response ----")
    print(response_text)

    response_json = json.loads(response_text)
    return response_json["relevant_files"]

# Get the tables from the files
def get_tables_from_files(file_names, data):
    table_names = []
    for file_name in file_names:
        if file_name in data:
            for table in data[file_name]:
                combined_str = f"{table['table_name']} : {table['table_description']}"
                table_names.append(combined_str)
    return table_names

# Pick the relevant tables
def pick_relevant_tables(client, tables, prompt):

    system_prompt = """You are a database expert that helps identify relevant tables
                    You must return your response as a valid JSON object with the following structure:
                    {
                        "relevant_tables": ["table1", "table2"]
                    }
                    Only include tables that are directly relevant to the user's query."""

    user_prompt = f"""Given the following user query:"{prompt}"
                    Which of these database tables are relevant?
                    Available tables: {tables}
                    Return only the relevant files in the specified JSON format."""

    print(system_prompt + "\n\n" + user_prompt)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": system_prompt + "\n\n" + user_prompt}]
    )
    response_text = response.choices[0].message.content

    # Clean up the response text
    response_text = response_text.replace('```json', '').replace('```', '').strip()
    print("---- pick_relevant_tables Response ----")
    print(response_text)

    response_json = json.loads(response_text)
    return response_json["relevant_tables"]

def grab_table_info(relevant_tables, file_names, data):

    table_info = []
    for file_name in file_names:
        if file_name in data:
            for table in data[file_name]:
                table_name = table['table_name']
                # Check if table_name is in any entry of relevant_tables
                if any(table_name in rt for rt in relevant_tables):
                    table_info.append({
                        'table_name': table_name,
                        'table_description': table['table_description'],
                        'columns': table['columns']
                    })
    return table_info

def generate_sql(client, relevant_tables, prompt, columns):

    system_prompt = """You are a database expert that helps generate SQL queries
                        You must return your response as a valid SQL query."""

    user_prompt = f"""Given the following user query: "{prompt}"
                    and these relevant tables: {relevant_tables}
                    and these relevant columns: {columns}
                    Return a sql query that will answer the user's query."""

    print("---- generate_sql Prompt ----")
    print(system_prompt + "\n\n" + user_prompt)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": system_prompt + "\n\n" + user_prompt}]
    )
    return response.choices[0].message.content

def run_full_process(api_key, user_prompt):
    """
      1) Reads table info from JSON files.
      2) Determines which files are relevant to the prompt.
      3) Determines which tables are relevant within those files.
      4) Gathers column-level info for those tables.
      5) Generates an SQL query to answer the prompt.

    Returns a dictionary with all intermediate data and the final query.
    """
    # 1) Gather data from JSON
    data = get_table_clusters()

    # 2) Create an OpenAI client
    client = create_openai_client(api_key)

    # 3) Find relevant files for this user query
    file_names = list(data.keys())
    relevant_files = get_relevant_files(client, file_names, user_prompt)

    # 4) Extract the tables from those files
    tables = get_tables_from_files(relevant_files, data)

    # 5) Pick relevant tables from that subset
    relevant_tables = pick_relevant_tables(client, tables, user_prompt)

    # 6) Get column info for those specific relevant tables
    columns_info = grab_table_info(relevant_tables, relevant_files, data)

    # 7) Generate final SQL
    sql_query = generate_sql(client, relevant_tables, user_prompt, columns_info)

    return {
        "all_data": data,
        "file_names": file_names,
        "relevant_files": relevant_files,
        "tables": tables,
        "relevant_tables": relevant_tables,
        "columns_info": columns_info,
        "final_sql_query": sql_query
    }

if __name__ == "__main__":
    # Example usage
    api_key = ""
    prompt = "I want to know the sales for the year 2024 for BLUE CHARGERS"
    results = run_full_process(api_key, prompt)

    print("\n---- Final SQL Query ----")
    print(results["final_sql_query"])
