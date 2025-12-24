from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template_string, request
import re
import os
import sys
import os


app = Flask(__name__)

# Groq API Configuration
try:
    from groq import Groq
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    
    if not GROQ_API_KEY:
        print("⚠️  Set GROQ_API_KEY environment variable")
        USE_AI = False
    else:
        groq_client = Groq(api_key=GROQ_API_KEY)
        USE_AI = True
        print("✅ Groq AI Ready")
except ImportError:
    USE_AI = False
    print("❌ Install: pip install groq")

def clean_sql_input(sql_text):
    """Remove SQL Server metadata and prepare for conversion"""
    # Remove everything before CREATE PROCEDURE
    lines = sql_text.splitlines()
    cleaned_lines = []
    found_create = False
    
    for line in lines:
        stripped = line.strip().lower()
        if not found_create:
            if stripped.startswith(("create procedure", "create proc", "alter procedure", "alter proc")):
                found_create = True
                cleaned_lines.append(line)
        else:
            if stripped not in ("go", ""):
                cleaned_lines.append(line)
    
    return "\n".join(cleaned_lines)

def groq_convert_sql(sql_text):
    """Use Groq AI with comprehensive conversion rules"""
    if not USE_AI:
        return None
    
    try:
        system_prompt = """You are an expert database migration specialist. You convert SQL Server T-SQL to PostgreSQL with 100% accuracy. You follow all conversion rules precisely and produce syntactically perfect PostgreSQL code."""

        user_prompt = f"""Convert this T-SQL stored procedure to PostgreSQL function following ALL these rules:

═══════════════════════════════════════════════════════════════════
COMPLETE T-SQL TO POSTGRESQL CONVERSION RULES
═══════════════════════════════════════════════════════════════════

1. PROCEDURE STRUCTURE:
   ✓ CREATE PROCEDURE [dbo].[Name] → CREATE OR REPLACE FUNCTION "dbo"."Name"
   ✓ ALTER PROCEDURE → CREATE OR REPLACE FUNCTION
   ✓ Must always include schema prefix "dbo".
   ✓ Remove all [brackets] around identifiers

2. PARAMETERS:
   ✓ @Parameter → p_Parameter (ALL parameters)
   ✓ @ID → p_ID, @Name → p_Name, @Count → p_Count
   ✓ Remove "AS" keyword: @ID AS INT → p_ID INTEGER
   ✓ Remove OUTPUT keyword
   ✓ Format: function_name(p_param1 TYPE, p_param2 TYPE)

3. VARIABLES (DECLARE):
   ✓ @Variable → v_Variable (ALL variables)
   ✓ @total → v_total, @count → v_count
   ✓ Move ALL DECLARE to DECLARE section after AS $$
   ✓ Format: v_variable_name TYPE;
   ✓ Handle comma-separated declares: DECLARE @a INT, @b INT → v_a INTEGER; v_b INTEGER;

4. DATA TYPE MAPPING (CRITICAL):
   ✓ INT → INTEGER
   ✓ BIGINT → BIGINT
   ✓ SMALLINT → SMALLINT
   ✓ TINYINT → SMALLINT
   ✓ BIT → BOOLEAN
   ✓ MONEY → NUMERIC(19,4)
   ✓ SMALLMONEY → NUMERIC(10,4)
   ✓ DECIMAL(p,s) → NUMERIC(p,s)
   ✓ NUMERIC(p,s) → NUMERIC(p,s)
   ✓ FLOAT → DOUBLE PRECISION
   ✓ REAL → REAL
   ✓ DATETIME → TIMESTAMP
   ✓ DATETIME2 → TIMESTAMP
   ✓ SMALLDATETIME → TIMESTAMP
   ✓ DATE → DATE
   ✓ TIME → TIME
   ✓ CHAR(n) → CHAR(n)
   ✓ VARCHAR(n) → VARCHAR(n)
   ✓ VARCHAR(MAX) → TEXT
   ✓ NCHAR(n) → CHAR(n)
   ✓ NVARCHAR(n) → VARCHAR(n)
   ✓ NVARCHAR(MAX) → TEXT
   ✓ TEXT → TEXT
   ✓ NTEXT → TEXT
   ✓ BINARY(n) → BYTEA
   ✓ VARBINARY(n) → BYTEA
   ✓ VARBINARY(MAX) → BYTEA
   ✓ IMAGE → BYTEA
   ✓ UNIQUEIDENTIFIER → UUID

5. FUNCTION CONVERSIONS:
   ✓ GETDATE() → CURRENT_TIMESTAMP
   ✓ GETUTCDATE() → CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
   ✓ SYSDATETIME() → CURRENT_TIMESTAMP
   ✓ ISNULL(a, b) → COALESCE(a, b)
   ✓ LEN(x) → LENGTH(x)
   ✓ CHARINDEX(find, str) → POSITION(find IN str)
   ✓ SUBSTRING(str, start, len) → SUBSTRING(str FROM start FOR len)
   ✓ LEFT(str, n) → LEFT(str, n) (same)
   ✓ RIGHT(str, n) → RIGHT(str, n) (same)
   ✓ LTRIM(str) → LTRIM(str) (same)
   ✓ RTRIM(str) → RTRIM(str) (same)
   ✓ UPPER(str) → UPPER(str) (same)
   ✓ LOWER(str) → LOWER(str) (same)
   ✓ REPLACE(str, find, repl) → REPLACE(str, find, repl) (same)
   ✓ CAST(x AS type) → CAST(x AS type)
   ✓ CONVERT(type, x) → CAST(x AS type)
   ✓ DATEADD(part, num, date) → date + INTERVAL 'num part'
   ✓ DATEDIFF(part, date1, date2) → EXTRACT(part FROM date2 - date1)
   ✓ YEAR(date) → EXTRACT(YEAR FROM date)
   ✓ MONTH(date) → EXTRACT(MONTH FROM date)
   ✓ DAY(date) → EXTRACT(DAY FROM date)
   ✓ DATENAME(part, date) → TO_CHAR(date, format)
   ✓ @@ROWCOUNT → GET DIAGNOSTICS var = ROW_COUNT
   ✓ @@IDENTITY → RETURNING clause or LASTVAL()
   ✓ SCOPE_IDENTITY() → LASTVAL()
   ✓ NEWID() → GEN_RANDOM_UUID()

6. IDENTIFIERS (MUST QUOTE ALL):
   ✓ Table names: Users → "Users", HR_Employee → "HR_Employee"
   ✓ Column names: UserID → "UserID", FirstName → "FirstName"
   ✓ Schema.Table: dbo.Users → "dbo"."Users" OR just "Users"
   ✓ Aliases: COUNT(*) AS total → COUNT(*) AS "total"
   ✓ In INSERT: INSERT INTO Users(ID, Name) → INSERT INTO "Users"("ID", "Name")
   ✓ In SELECT: SELECT ID, Name FROM Users → SELECT "ID", "Name" FROM "Users"
   ✓ In WHERE: WHERE UserID = 1 → WHERE "UserID" = 1
   ✓ In JOIN: ON a.ID = b.UserID → ON a."ID" = b."UserID"

7. RETURNS CLAUSE (CRITICAL):
   ✓ If procedure ONLY has INSERT/UPDATE/DELETE → RETURNS VOID
   ✓ If procedure has SELECT that returns data → RETURNS TABLE(columns...)
   ✓ Analyze SELECT columns to determine types
   ✓ Example: SELECT ID, Name, Age → RETURNS TABLE("ID" INTEGER, "Name" VARCHAR, "Age" INTEGER)

8. RETURN QUERY:
   ✓ For SELECT that returns data: Add RETURN QUERY before SELECT
   ✓ Example: SELECT * FROM Users → RETURN QUERY SELECT * FROM "Users";

9. SELECT INTO / ASSIGNMENT:
   ✓ SELECT @var = col FROM table → SELECT "col" INTO v_var FROM "table" LIMIT 1;
   ✓ SELECT TOP 1 @var = col → SELECT "col" INTO v_var FROM "table" LIMIT 1;
   ✓ SET @var = value → v_var := value;

10. TOP CLAUSE:
    ✓ SELECT TOP n columns → SELECT columns LIMIT n
    ✓ SELECT TOP 1 → SELECT ... LIMIT 1

11. CURSORS:
    ✓ DECLARE cursor_name CURSOR FOR SELECT → FOR record_var IN SELECT ... LOOP
    ✓ OPEN cursor_name → (remove)
    ✓ FETCH NEXT FROM cursor INTO @vars → record_var.column_name
    ✓ WHILE @@FETCH_STATUS = 0 BEGIN ... END → LOOP ... END LOOP;
    ✓ CLOSE cursor_name → (remove)
    ✓ DEALLOCATE cursor_name → (remove)
    ✓ Add: record_var RECORD; to DECLARE section

12. EXEC/EXECUTE:
    ✓ EXEC procedure_name @p1, @p2 → PERFORM "dbo"."procedure_name"(v_p1, v_p2);
    ✓ EXECUTE procedure → PERFORM "dbo"."procedure"();
    ✓ Convert @parameters to v_variables if they're local variables

13. IF/ELSE:
    ✓ IF condition BEGIN ... END → IF condition THEN ... END IF;
    ✓ IF...ELSE → IF...THEN...ELSE...END IF;
    ✓ No BEGIN/END needed in PostgreSQL IF blocks

14. WHILE LOOPS:
    ✓ WHILE condition BEGIN ... END → WHILE condition LOOP ... END LOOP;

15. TRY/CATCH:
    ✓ BEGIN TRY ... END TRY BEGIN CATCH ... END CATCH → BEGIN ... EXCEPTION WHEN OTHERS THEN ... END;

16. TRANSACTIONS:
    ✓ BEGIN TRANSACTION → BEGIN;
    ✓ COMMIT TRANSACTION → COMMIT;
    ✓ ROLLBACK TRANSACTION → ROLLBACK;

17. TEMPORARY TABLES:
    ✓ #TempTable → TEMP TABLE or regular table
    ✓ CREATE TABLE #temp → CREATE TEMP TABLE temp

18. IDENTITY/SERIAL:
    ✓ INT IDENTITY(1,1) → SERIAL or INTEGER GENERATED ALWAYS AS IDENTITY
    ✓ BIGINT IDENTITY(1,1) → BIGSERIAL

19. OUTPUT CLAUSE:
    ✓ INSERT...OUTPUT INSERTED.* → INSERT...RETURNING *
    ✓ UPDATE...OUTPUT DELETED.*, INSERTED.* → (use RETURNING)

20. AGGREGATE FUNCTIONS:
    ✓ COUNT(*), SUM(), AVG(), MIN(), MAX() → Same syntax
    ✓ COUNT_BIG() → COUNT()

21. STRING CONCATENATION:
    ✓ 'str1' + 'str2' → 'str1' || 'str2'
    ✓ Use CONCAT() function for NULL safety

22. CASE EXPRESSIONS:
    ✓ Same syntax in both (no changes needed)

23. COMMENTS:
    ✓ Remove SQL Server metadata comments (-- ===, /****** Object: ...)
    ✓ Keep business logic comments

24. STRUCTURE FORMAT:
    ✓ Use AS $$ ... $$ delimiters (NOT single quotes)
    ✓ Add LANGUAGE plpgsql
    ✓ End with $$;
    ✓ Proper indentation (4 spaces)
    ✓ All statements end with semicolon

25. REMOVE THESE:
    ✓ GO statements
    ✓ USE [database] statements
    ✓ SET ANSI_NULLS ON/OFF
    ✓ SET QUOTED_IDENTIFIER ON/OFF
    ✓ SET NOCOUNT ON/OFF
    ✓ WITH (RECOMPILE)
    ✓ WITH ENCRYPTION
    ✓ [dbo] brackets (convert to "dbo" or remove)

═══════════════════════════════════════════════════════════════════

T-SQL INPUT:
```sql
{sql_text}
```

INSTRUCTIONS:
1. Apply ALL conversion rules above
2. Quote ALL table and column names with double quotes
3. Ensure proper RETURNS clause (VOID or TABLE)
4. Add RETURN QUERY for SELECT that returns data
5. Convert ALL @vars to p_ (params) or v_ (variables)
6. Use correct PostgreSQL syntax throughout
7. Return ONLY the PostgreSQL code, no explanations

PostgreSQL OUTPUT:"""

        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.05,  # Very low for accuracy
            max_tokens=8000,
            top_p=0.9
        )
        
        result = completion.choices[0].message.content.strip()
        
        # Clean markdown
        result = re.sub(r'^```(?:sql|postgresql)?\s*\n', '', result, flags=re.IGNORECASE)
        result = re.sub(r'\n```\s*$', '', result)
        result = result.strip()
        
        return result
    
    except Exception as e:
        print(f"❌ Groq Error: {e}")
        return None

def validate_postgresql(pg_sql):
    """Validate PostgreSQL output"""
    issues = []
    
    required_patterns = {
        r'CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION': "Missing CREATE FUNCTION",
        r'RETURNS\s+(?:VOID|TABLE|SETOF)': "Missing RETURNS clause",
        r'LANGUAGE\s+plpgsql': "Missing LANGUAGE plpgsql",
        r'AS\s+\$\$': "Missing AS $$ delimiter",
        r'\$\$\s*;?\s*$': "Missing closing $$"
    }
    
    for pattern, message in required_patterns.items():
        if not re.search(pattern, pg_sql, re.IGNORECASE):
            issues.append(message)
    
    # Check for T-SQL remnants
    remnants = {
        r'@\w+': "Contains @ symbols (should be p_ or v_)",
        r'\bGO\b': "Contains GO statement",
        r'CREATE\s+PROCEDURE': "Contains CREATE PROCEDURE",
        r'SET\s+NOCOUNT': "Contains SET NOCOUNT",
        r'GETDATE\(\)': "Contains GETDATE() (should be CURRENT_TIMESTAMP)"
    }
    
    for pattern, message in remnants.items():
        if re.search(pattern, pg_sql, re.IGNORECASE):
            issues.append(message)
    
    return issues

def convert_to_postgresql(sql_text):
    """Main conversion function"""
    if not sql_text or not sql_text.strip():
        return "-- Error: Empty input"
    
    sql_text = clean_sql_input(sql_text)
    
    if not sql_text:
        return "-- Error: No CREATE PROCEDURE found"
    
    if USE_AI:
        print("🤖 Converting with Groq AI (Llama 3.3 70B)...")
        result = groq_convert_sql(sql_text)
        
        if result:
            issues = validate_postgresql(result)
            
            if issues:
                warning = "-- ⚠️  Validation Warnings:\n"
                for issue in issues:
                    warning += f"-- • {issue}\n"
                warning += "-- Please review carefully.\n\n"
                return warning + result
            else:
                return "-- ✅ Conversion Successful & Validated\n\n" + result
        else:
            return "-- ❌ AI conversion failed. Check API key and connection."
    else:
        return """-- ❌ Groq AI Not Configured

To enable accurate conversion:
1. Get free API key: https://console.groq.com
2. Install: pip install groq  
3. Set: export GROQ_API_KEY='your-key'
4. Restart application

Without AI, accurate conversion is not guaranteed."""

HTML = '''<!doctype html>
<html><head><title>Complete T-SQL to PostgreSQL Converter</title>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;padding:20px}
.container{max-width:1600px;margin:0 auto;background:#fff;padding:40px;border-radius:16px;box-shadow:0 25px 70px rgba(0,0,0,0.35)}
.header{text-align:center;margin-bottom:30px}
h1{color:#1e293b;font-size:2.8rem;font-weight:900;margin-bottom:8px}
.subtitle{color:#64748b;font-size:1.1rem;margin-bottom:20px}
.badge{display:inline-block;padding:10px 24px;border-radius:30px;font-size:0.95rem;font-weight:700;color:#fff;background:linear-gradient(135deg,''' + ('#10b981,#059669' if USE_AI else '#94a3b8,#64748b') + ''');box-shadow:0 4px 15px rgba(0,0,0,0.2)}
.features{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:15px;margin:25px 0;padding:20px;background:#f8fafc;border-radius:12px}
.feature{display:flex;align-items:center;gap:10px;padding:12px;background:#fff;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.08)}
.feature-icon{font-size:1.5rem}
.feature-text{font-size:0.9rem;color:#475569;font-weight:600}
.setup{background:#fef3c7;border-left:4px solid #f59e0b;padding:20px;margin:20px 0;border-radius:8px;display:''' + ('none' if USE_AI else 'block') + '''}
.upload{text-align:center;padding:40px;border:3px dashed #667eea;border-radius:12px;margin:25px 0;background:linear-gradient(135deg,#f8faff,#f0f4ff);transition:all 0.3s}
.upload:hover{border-color:#764ba2;transform:translateY(-2px)}
input[type="file"]{display:none}
.file-label{padding:16px 40px;background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;border-radius:12px;cursor:pointer;font-weight:700;display:inline-block;transition:all 0.3s;box-shadow:0 4px 15px rgba(102,126,234,0.4)}
.file-label:hover{transform:translateY(-3px);box-shadow:0 8px 25px rgba(102,126,234,0.6)}
.file-name{margin-top:15px;color:#64748b;font-weight:600}
.editor{display:grid;grid-template-columns:1fr 1fr;gap:25px;margin:25px 0}
.panel{background:#f8fafc;padding:20px;border-radius:12px;border:2px solid #e2e8f0}
.panel h3{color:#1e293b;margin-bottom:15px;font-size:1.1rem;font-weight:700;display:flex;align-items:center;gap:10px}
textarea{width:100%;height:550px;padding:18px;font-family:'Fira Code','Cascadia Code','Consolas',monospace;font-size:13.5px;border:2px solid #cbd5e1;border-radius:10px;resize:vertical;line-height:1.7;background:#fff;color:#1e293b}
textarea:focus{outline:none;border-color:#667eea;box-shadow:0 0 0 4px rgba(102,126,234,0.15)}
textarea[readonly]{background:#f1f5f9}
.buttons{display:flex;justify-content:center;gap:15px;margin-top:30px}
button{padding:16px 45px;border:none;border-radius:12px;font-size:1.05rem;font-weight:700;cursor:pointer;transition:all 0.3s;box-shadow:0 4px 15px rgba(0,0,0,0.15)}
.btn-primary{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff}
.btn-primary:hover:not(:disabled){transform:translateY(-3px);box-shadow:0 8px 25px rgba(102,126,234,0.5)}
.btn-secondary{background:#64748b;color:#fff}
.btn-secondary:hover:not(:disabled){transform:translateY(-3px);box-shadow:0 8px 25px rgba(100,116,139,0.4)}
button:disabled{opacity:0.5;cursor:not-allowed;transform:none}
@media (max-width:1200px){.editor{grid-template-columns:1fr}.features{grid-template-columns:1fr}}
</style></head><body>
<div class="container">
<div class="header">
<h1>🚀 Complete T-SQL to PostgreSQL Converter</h1>
<p class="subtitle">AI-Powered Migration with 25+ Conversion Rules</p>
<span class="badge">''' + ('✅ AI ACTIVE - Groq Llama 3.3 70B' if USE_AI else '⚠️ CONFIGURE AI FOR ACCURACY') + '''</span>
</div>

<div class="features">
<div class="feature"><span class="feature-icon">✓</span><span class="feature-text">All Data Types</span></div>
<div class="feature"><span class="feature-icon">✓</span><span class="feature-text">Functions & Procedures</span></div>
<div class="feature"><span class="feature-icon">✓</span><span class="feature-text">Cursors to Loops</span></div>
<div class="feature"><span class="feature-icon">✓</span><span class="feature-text">Variables & Parameters</span></div>
<div class="feature"><span class="feature-icon">✓</span><span class="feature-text">All SQL Functions</span></div>
<div class="feature"><span class="feature-icon">✓</span><span class="feature-text">Complete Quoting</span></div>
<div class="feature"><span class="feature-icon">✓</span><span class="feature-text">Smart Returns</span></div>
<div class="feature"><span class="feature-icon">✓</span><span class="feature-text">Validated Output</span></div>
</div>

''' + ('''<div class="setup">
<strong>⚡ Setup AI (2 minutes):</strong><br>
1. Visit <a href="https://console.groq.com" target="_blank" style="font-weight:700">console.groq.com</a> → Create free account<br>
2. Generate API key from dashboard<br>
3. Run: <code style="background:#fff;padding:4px 8px;border-radius:4px">pip install groq</code><br>
4. Set: <code style="background:#fff;padding:4px 8px;border-radius:4px">export GROQ_API_KEY="your-key"</code><br>
5. Restart app
</div>''' if not USE_AI else '') + '''

<div class="upload">
<form method="post" enctype="multipart/form-data">
<label for="fileInput" class="file-label">📁 Upload SQL File</label>
<input type="file" id="fileInput" name="file" accept=".sql" onchange="handleFile(this)">
<div class="file-name" id="fileName">No file selected</div>
</form>
</div>

<form method="post">
<div class="editor">
<div class="panel">
<h3><span>📝</span> T-SQL Input</h3>
<textarea name="sql_text" id="sqlInput" placeholder="Paste your SQL Server T-SQL code here...">{{sql_text}}</textarea>
</div>
<div class="panel">
<h3><span>✅</span> PostgreSQL Output</h3>
<textarea readonly id="sqlOutput" placeholder="Converted PostgreSQL code will appear here...">{{converted}}</textarea>
</div>
</div>
<div class="buttons">
<button type="submit" class="btn-primary">🔄 Convert with AI</button>
<button type="button" class="btn-secondary" onclick="copy()" {%if not converted%}disabled{%endif%}>📋 Copy</button>
<button type="button" class="btn-secondary" onclick="download()" {%if not converted%}disabled{%endif%}>💾 Download</button>
<button type="button" class="btn-secondary" onclick="clear()">🗑️ Clear</button>
</div>
</form>
</div>
<script>
let fileName='';
function handleFile(input){
const file=input.files[0];
if(file){
    fileName = file.name.replace(/\.sql$/i, "");


document.getElementById('fileName').textContent='📄 '+file.name;
const reader=new FileReader();
reader.onload=e=>document.getElementById('sqlInput').value=e.target.result;
reader.readAsText(file);
}}
function copy(){
const el=document.getElementById('sqlOutput');
el.select();
document.execCommand('copy');
alert('✅ Copied to clipboard!');
}
function download(){
    const content = document.getElementById('sqlOutput').value;
    if (!content) return alert('No valid output to download');

    // ✅ If no file was uploaded, fallback name
    let name = fileName ? fileName + "_pg.sql" : "converted_pg.sql";

    const blob = new Blob([content], {type: 'text/plain;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
}


function clear(){
if(confirm('Clear all content?')){
document.getElementById('sqlInput').value='';
document.getElementById('sqlOutput').value='';
document.getElementById('fileName').textContent='No file selected';
fileName='';
}}
</script>
</body></html>'''

@app.route('/', methods=['GET', 'POST'])
def index():
    sql_text = ''
    converted = ''
    if request.method == 'POST':
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            sql_text = file.read().decode('utf-8')
        else:
            sql_text = request.form.get('sql_text', '')
        
        if sql_text:
            try:
                converted = convert_to_postgresql(sql_text)
            except Exception as e:
                import traceback
                converted = f'-- ❌ Error:\n-- {str(e)}\n--\n{traceback.format_exc()}'
    
    return render_template_string(HTML, sql_text=sql_text, converted=converted)

if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("  🚀 COMPLETE T-SQL TO POSTGRESQL CONVERTER WITH AI".center(80))
    print("=" * 80)
    if USE_AI:
        print("  ✅ AI STATUS: ENABLED".center(80))
        print("  🧠 MODEL: Groq Llama 3.3 70B Versatile".center(80))
        print("  📋 RULES: 25+ Comprehensive Conversion Patterns".center(80))
    else:
        print("  ⚠️  AI STATUS: NOT CONFIGURED".center(80))
        print("  Setup: https://console.groq.com → Get Free API Key".center(80))
    print("=" * 80)
    print(f"  🌐 Access: http://127.0.0.1:5001".center(80))
    print("=" * 80 + "\n")
    import webbrowser
    webbrowser.open("http://127.0.0.1:5001")

    app.run(host='127.0.0.1', port=5001, debug=False)