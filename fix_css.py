import re

# Read the current CSS file
with open(r'f:\网站\谷歌\static\style.css', 'r', encoding='utf-8') as f:
    content = f.read()

# Define the missing history styles
history_styles = '''
.history-list::-webkit-scrollbar-thumb {
    background: rgba(99, 102, 241, 0.3);
    border-radius: 3px;
}

.history-list::-webkit-scrollbar-thumb:hover {
    background: rgba(99, 102, 241, 0.5);
}

.history-item {
    background: rgba(30, 34, 53, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    display: flex;
    flex-direction: column;
    margin-bottom: 4px;
}

.history-item:hover {
    background: rgba(30, 34, 53, 0.8);
    border-color: var(--primary-color);
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

.history-thumb {
    width: 100%;
    height: 160px;
    object-fit: cover;
    background: #1e2235;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    transition: transform 0.3s ease;
}

.history-item:hover .history-thumb {
    transform: scale(1.02);
}

.history-info {
    padding: 12px 14px;
    background: linear-gradient(to bottom, rgba(30, 34, 53, 0), rgba(30, 34, 53, 0.5));
}

.history-prompt {
    font-size: 13px;
    color: var(--text-main);
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    margin-bottom: 10px;
    font-weight: 500;
    opacity: 0.9;
}

.history-meta {
    font-size: 11px;
    color: var(--text-muted);
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 10px;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.history-meta span {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.03);
    padding: 4px 8px;
    border-radius: 4px;
    font-weight: 500;
}
'''

# Find the position after .history-list::-webkit-scrollbar-track
pattern = r'(\.history-list::-webkit-scrollbar-track\s*\{[^}]+\})'
match = re.search(pattern, content)

if match:
    # Insert the history styles after the scrollbar-track definition
    insert_pos = match.end()
    new_content = content[:insert_pos] + '\n' + history_styles + content[insert_pos:]
    
    # Write back to file
    with open(r'f:\网站\谷歌\static\style.css', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✅ History styles successfully added!")
else:
    print("❌ Could not find insertion point")
