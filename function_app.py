import azure.functions as func
import logging, requests, json, os, uuid
from datetime import datetime, timezone
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableServiceClient
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
from azure.data.tables import TableServiceClient

AI_ENDPOINT = os.environ['AI_LANGUAGE_ENDPOINT']
AI_KEY = os.environ['AI_LANGUAGE_KEY']
CONTAINER_APP_URL = os.environ['CONTAINER_APP_URL']
CONN_STR = os.environ['AZURE_STORAGE_CONNECTION_STRING']


app = func.FunctionApp()

@app.route(route="TriggerCompile", auth_level=func.AuthLevel.ANONYMOUS)
def TriggerCompile(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        code = body.get('code', '')
        user_id = body.get('userId', 'anonymous')
        opt_level = body.get('optimization', 'O2')
        language = body.get('language', 'c')

        # Upload code to Blob Storage
        blob_svc = BlobServiceClient.from_connection_string(CONN_STR)
        job_id = str(uuid.uuid4())
        blob_client = blob_svc.get_blob_client('code-uploads', f'{job_id}.c')
        blob_client.upload_blob(code.encode(), overwrite=True)

        # Call Container App to compile
        response = requests.post(
            f'https://{CONTAINER_APP_URL}/compile',
            json={'code': code, 'optimization': opt_level, 'language': language},
            timeout=60
        )
        result = response.json()
        # Get first result for exec time
        first_result = next(iter(result.values()), {})

        # Save output to Blob
        out_blob = blob_svc.get_blob_client('compiled-outputs', f'{job_id}_result.json')
        out_blob.upload_blob(json.dumps(result).encode(), overwrite=True)

        # Save history to Azure Table Storage
        table_svc = TableServiceClient.from_connection_string(CONN_STR)
        table_client = table_svc.get_table_client('CompilationHistory')
        table_client.create_entity({
            'PartitionKey': user_id,
            'RowKey': job_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'optimization': opt_level,
            'language': language,                        
            'success': any(r.get('success') for r in result.values()),
            'codeLength': len(code),
            'execTimeMs': str(first_result.get('exec_time_ms', '')),  
        })

        return func.HttpResponse(json.dumps({
            'jobId': job_id,
            'results': result
        }), mimetype='application/json', status_code=200)

    except Exception as e:
        return func.HttpResponse(json.dumps({'error': str(e)}),
            mimetype='application/json', status_code=500)

def get_ai_explanation(error_text):
    client = TextAnalyticsClient(AI_ENDPOINT, AzureKeyCredential(AI_KEY))
    # Extract key phrases to understand error categories
    response = client.extract_key_phrases([error_text])
    phrases = response[0].key_phrases if not response[0].is_error else []

    # Build structured explanation based on error content
    explanation = build_explanation(error_text, phrases)
    return explanation

def build_explanation(error, phrases):
    rules = {
        # C / C++
        'undeclared': ('Undeclared Variable', 'You used a variable that was never declared. Add the type before the variable name.'),
        'syntax error': ('Syntax Error', 'Your code has a syntax mistake. Check for missing semicolons, brackets, or parentheses.'),
        'undefined reference': ('Linker Error', 'Function exists in header but not defined. Add the implementation or link the library.'),
        'implicit': ('Implicit Declaration', 'Function used before declaring it. Add a prototype or #include the correct header.'),
        'segmentation': ('Segfault Risk', 'Memory access violation. Check array bounds and pointer dereferences.'),
        # Python
        'syntaxerror': ('Python Syntax Error', 'Your Python code has a syntax mistake. Check for missing colons after def/if/for, wrong indentation, or unclosed brackets.'),
        'nameerror': ('Python Name Error', 'You used a variable or function name that does not exist. Check spelling or make sure it is defined before use.'),
        'typeerror': ('Python Type Error', 'You are using the wrong data type. For example passing a string where a number is expected, or calling a non-function.'),
        'indentationerror': ('Python Indentation Error', 'Your indentation is inconsistent. Use 4 spaces consistently — do not mix tabs and spaces.'),
        'indexerror': ('Python Index Error', 'You are accessing a list index that does not exist. Check your list length before accessing elements.'),
        'attributeerror': ('Python Attribute Error', 'You are calling a method or property that does not exist on this object. Check the variable type.'),
        'importerror': ('Python Import Error', 'The module you are trying to import does not exist or is not installed.'),
        'zerodivisionerror': ('Division by Zero', 'Your code is dividing by zero. Add a check before dividing.'),
        # Java
        'cannot find symbol': ('Java Undefined Symbol', 'You used a variable, method, or class that was never declared. Check spelling and scope.'),
        'reached end of file': ('Java Missing Brace', 'Your code is missing a closing brace. Make sure every { has a matching }.'),
        'incompatible types': ('Java Type Mismatch', 'You are assigning the wrong type to a variable. Check that both sides of the assignment match.'),
        'missing return': ('Java Missing Return', 'Your method is supposed to return a value but is missing a return statement.'),
        # Rust
        'expected': ('Rust Syntax Error', 'Rust expected a different token. Check for missing semicolons, brackets, or incorrect syntax.'),
        'cannot borrow': ('Rust Borrow Error', 'Rust ownership rules are violated. A value is being borrowed while already borrowed elsewhere.'),
        'mismatched types': ('Rust Type Mismatch', 'The types on both sides do not match. Check your variable declarations and return types.'),
        'use of undeclared': ('Rust Undeclared Variable', 'You used a variable that was never declared. Declare it with let before using it.'),
        # Go
        'declared but not used': ('Go Unused Variable', 'Go does not allow declared variables that are never used. Either use the variable or remove it.'),
        'undefined:': ('Go Undefined Reference', 'You referenced something that does not exist. Check spelling and imports.'),
        'cannot use': ('Go Type Mismatch', 'You are using the wrong type. Go is strictly typed — make sure types match exactly.'),
    }
    for key, (title, fix) in rules.items():
        if key in error.lower():
            return {'errorType': title, 'explanation': fix, 'keyPhrases': phrases}
    return {'errorType': 'Compilation Error', 'explanation': 'Check your code carefully. Key elements: ' + ', '.join(phrases[:5]), 'keyPhrases': phrases}


@app.route(route="ExplainError", auth_level=func.AuthLevel.ANONYMOUS)
def ExplainError(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        error_text = body.get('error', '')
        explanation = get_ai_explanation(error_text)

        # Track error type in Azure Table Storage
        table_svc = TableServiceClient.from_connection_string(CONN_STR)
        table_client = table_svc.get_table_client('ErrorTypes')
        table_client.upsert_entity({
            'PartitionKey': 'errors',
            'RowKey': str(uuid.uuid4()),
            'errorCategory': explanation['errorType'],
        })

        return func.HttpResponse(json.dumps(explanation),
            mimetype='application/json', status_code=200)
    except Exception as e:
        return func.HttpResponse(json.dumps({'error': str(e)}),
            mimetype='application/json', status_code=500)

@app.route(route="GetHistory", auth_level=func.AuthLevel.ANONYMOUS)
def GetHistory(req: func.HttpRequest) -> func.HttpResponse:
    user_id = req.params.get('userId', 'anonymous')
    table_svc = TableServiceClient.from_connection_string(CONN_STR)
    table_client = table_svc.get_table_client('CompilationHistory')
    # Query by PartitionKey (userId) - Table Storage native filtering
    entities = list(table_client.query_entities(
    query_filter=f"PartitionKey eq '{user_id}'",
    select=['RowKey', 'timestamp', 'optimization', 'success', 
            'codeLength', 'language', 'execTimeMs'] 
))
    # Sort by timestamp descending, return latest 20
    entities.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return func.HttpResponse(json.dumps(entities[:20], default=str),
        mimetype='application/json')


