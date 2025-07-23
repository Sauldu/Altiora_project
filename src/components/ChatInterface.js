import React, { useState, useRef, useEffect } from 'react';

const ChatInterface = () => {
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState([
    {
      id: 1,
      sender: 'altiora',
      text: "👋 Bonjour ! Je suis Altiora, votre assistant QA. Je peux analyser des SFD, générer des tests Playwright, ou vous aider avec vos matrices de test. Comment puis-je vous aider ?",
      timestamp: new Date().toISOString(),
      type: 'greeting'
    }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState(null);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // Auto-scroll vers le bas
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Analyse de l'intention utilisateur
  const analyzeIntent = (text) => {
    const lowerText = text.toLowerCase();
    
    if (lowerText.includes('sfd') || lowerText.includes('spécification')) {
      return 'analyze_sfd';
    } else if (lowerText.includes('test') && lowerText.includes('génér')) {
      return 'generate_tests';
    } else if (lowerText.includes('matrice')) {
      return 'create_matrix';
    } else if (lowerText.includes('exécut') || lowerText.includes('lanc')) {
      return 'execute_tests';
    } else if (lowerText.includes('rapport') || lowerText.includes('résultat')) {
      return 'show_reports';
    } else if (lowerText.includes('aide') || lowerText.includes('help')) {
      return 'help';
    }
    
    return 'general';
  };

  // Traitement des requêtes selon l'intention
  const processUserRequest = async (intent, text, file) => {
    // Simulation des réponses API
    switch (intent) {
      case 'analyze_sfd':
        if (!file) {
          return {
            text: "📎 Veuillez d'abord télécharger votre fichier SFD (PDF, Word ou texte).",
            type: 'request_file'
          };
        }
        
        // Simulation d'analyse SFD
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        return {
          text: `✅ J'ai analysé votre SFD. Voici ce que j'ai trouvé :
          
**3 scénarios identifiés**
1. Connexion utilisateur [Critique]
2. Réinitialisation mot de passe [Haute]
3. Déconnexion [Normale]

Souhaitez-vous que je génère les tests Playwright pour ces scénarios ?`,
          data: { scenarios: 3 },
          type: 'sfd_analysis'
        };

      case 'generate_tests':
        await new Promise(resolve => setTimeout(resolve, 1500));
        
        return {
          text: `🚀 J'ai généré 3 tests Playwright pour vous :`,
          data: {
            tests: [
              {
                name: 'test_login_success',
                code: `async def test_login_success(page):
    await page.goto("https://app.example.com/login")
    await page.fill("#email", "user@test.com")
    await page.fill("#password", "password123")
    await page.click("button[type='submit']")
    await expect(page).to_have_url("https://app.example.com/dashboard")`
              },
              {
                name: 'test_login_failure',
                code: `async def test_login_failure(page):
    await page.goto("https://app.example.com/login")
    await page.fill("#email", "user@test.com")
    await page.fill("#password", "wrongpass")
    await page.click("button[type='submit']")
    await expect(page.locator(".error")).to_contain_text("Invalid credentials")`
              }
            ]
          },
          type: 'tests_generated'
        };

      case 'help':
        return {
          text: `📚 **Voici ce que je peux faire pour vous :**

• **Analyser des SFD** : Envoyez-moi un PDF, Word ou fichier texte
• **Générer des tests** : Je crée des tests Playwright à partir de vos scénarios  
• **Créer des matrices** : Matrices de test, de couverture ou de traçabilité
• **Exécuter des tests** : Lancer vos suites de tests automatisés
• **Consulter les rapports** : Voir les résultats et métriques

💡 **Exemples de commandes :**
- "Analyse cette SFD" (avec fichier joint)
- "Génère des tests pour le module de connexion"
- "Crée une matrice de test"`,
          type: 'help'
        };

      default:
        return {
          text: "🤔 Je ne suis pas sûr de comprendre. Pouvez-vous reformuler ou tapez 'aide' pour voir ce que je peux faire ?",
          type: 'clarification'
        };
    }
  };

  // Gestion de l'envoi de message
  const handleSend = async () => {
    if (!message.trim() && !uploadedFile) return;

    const userMessage = {
      id: Date.now(),
      sender: 'user',
      text: message,
      file: uploadedFile,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setMessage('');
    setIsLoading(true);

    try {
      const intent = analyzeIntent(message);
      const response = await processUserRequest(intent, message, uploadedFile);
      
      const altioraMessage = {
        id: Date.now() + 1,
        sender: 'altiora',
        text: response.text,
        data: response.data,
        type: response.type,
        timestamp: new Date().toISOString()
      };

      setMessages(prev => [...prev, altioraMessage]);
      setUploadedFile(null);
    } catch (error) {
      const errorMessage = {
        id: Date.now() + 1,
        sender: 'altiora',
        text: `❌ Désolé, une erreur s'est produite : ${error.message}`,
        type: 'error',
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  // Gestion upload fichier
  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      setUploadedFile(file);
    }
  };

  // Rendu des messages selon leur type
  const renderMessage = (msg) => {
    if (msg.type === 'tests_generated' && msg.data) {
      return (
        <div className="space-y-2">
          <p className="text-gray-100 mb-3">{msg.text}</p>
          {msg.data.tests.map((test, idx) => (
            <div key={idx} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <div className="text-blue-400 font-mono text-sm mb-2">{test.name}</div>
              <pre className="text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap font-mono bg-gray-900 p-3 rounded">
{test.code}
              </pre>
              <button className="mt-3 px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Exécuter ce test
              </button>
            </div>
          ))}
        </div>
      );
    }

    // Format multi-ligne avec ** pour le gras
    const formattedText = msg.text.split('\n').map((line, i) => {
      // Remplacer **text** par du gras
      const parts = line.split(/(\*\*[^*]+\*\*)/g);
      return (
        <span key={i}>
          {parts.map((part, j) => {
            if (part.startsWith('**') && part.endsWith('**')) {
              return <strong key={j}>{part.slice(2, -2)}</strong>;
            }
            return part;
          })}
          {i < msg.text.split('\n').length - 1 && <br />}
        </span>
      );
    });

    return <p className="text-gray-100">{formattedText}</p>;
  };

  // Format timestamp
  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-blue-600 p-4 shadow-lg">
        <h2 className="text-xl font-bold">Assistant Altiora</h2>
        <p className="text-sm text-blue-100">IA de test automatisé</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-900">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`flex gap-3 max-w-[70%] ${msg.sender === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
              <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                msg.sender === 'user' ? 'bg-green-600' : 'bg-blue-600'
              }`}>
                {msg.sender === 'user' ? 'U' : 'A'}
              </div>
              
              <div className={`rounded-lg p-4 ${
                msg.sender === 'user' ? 'bg-green-800' : 'bg-gray-800'
              }`}>
                {msg.file && (
                  <div className="inline-flex items-center gap-2 px-2 py-1 bg-gray-700 rounded text-sm mb-2">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                    </svg>
                    {msg.file.name}
                  </div>
                )}
                {renderMessage(msg)}
                <div className="text-xs text-gray-400 mt-2">
                  {formatTime(msg.timestamp)}
                </div>
              </div>
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex items-center gap-2 ml-14 text-gray-400">
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
            <span className="text-sm">Altiora réfléchit...</span>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Fichier uploadé */}
      {uploadedFile && (
        <div className="px-4 py-2 bg-gray-800 border-t border-gray-700">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-gray-700 rounded text-sm">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
            </svg>
            {uploadedFile.name}
            <button 
              onClick={() => setUploadedFile(null)}
              className="ml-2 text-gray-400 hover:text-white"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Input */}
      <div className="p-4 bg-gray-800 border-t border-gray-700">
        <div className="flex gap-2">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            className="hidden"
            accept=".pdf,.doc,.docx,.txt"
          />
          
          <button 
            onClick={() => fileInputRef.current?.click()}
            className="p-2 hover:bg-gray-700 rounded transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
            </svg>
          </button>
          
          <textarea
            className="flex-1 bg-gray-700 text-white p-3 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Demandez-moi d'analyser une SFD, générer des tests..."
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            rows={1}
            style={{ minHeight: '44px', maxHeight: '120px' }}
          />
          
          <button 
            onClick={handleSend}
            disabled={(!message.trim() && !uploadedFile) || isLoading}
            className={`px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${
              (!message.trim() && !uploadedFile) || isLoading 
                ? 'bg-gray-700 text-gray-500 cursor-not-allowed' 
                : 'bg-blue-600 hover:bg-blue-700 text-white'
            }`}
          >
            Envoyer
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;