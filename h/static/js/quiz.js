// Quiz functionality
class Quiz {
    constructor(subject) {
        this.subject = subject;
        this.questions = [];
        this.currentQuestionIndex = 0;
        this.score = 0;
        this.quizContainer = document.getElementById('quiz-container');
        this.questionElement = document.getElementById('question');
        this.optionsContainer = document.getElementById('options');
        this.nextButton = document.getElementById('next-btn');
        this.resultContainer = document.getElementById('result');
        this.scoreElement = document.getElementById('score');
        this.progressBar = document.getElementById('progress-bar');
        this.timerElement = document.getElementById('timer');
        this.timeLeft = 600; // 10 minutes in seconds
        this.timer = null;
        this.userAnswers = [];
        
        this.initialize();
    }

    async initialize() {
        try {
            // Fetch questions from the API
            const response = await fetch(`/api/questions/${this.subject}`, {
                credentials: 'same-origin'
            });
            if (!response.ok) {
                throw new Error('Failed to load questions');
            }
            this.questions = await response.json();
            
            if (this.questions.length === 0) {
                throw new Error('No questions available');
            }
            
            this.showQuestion();
            this.startTimer();
            this.nextButton.addEventListener('click', () => this.nextQuestion());
            
        } catch (error) {
            console.error('Error initializing quiz:', error);
            this.quizContainer.innerHTML = `
                <div class="error">
                    <h2>Error Loading Quiz</h2>
                    <p>${error.message}</p>
                    <a href="/" class="btn">Return to Home</a>
                </div>
            `;
        }
    }

    showQuestion() {
        if (this.currentQuestionIndex >= this.questions.length) {
            this.showResult();
            return;
        }

        const question = this.questions[this.currentQuestionIndex];
        this.questionElement.textContent = `${this.currentQuestionIndex + 1}. ${question.question}`;
        
        // Clear previous options
        this.optionsContainer.innerHTML = '';
        
        // Add new options
        question.options.forEach((option, index) => {
            const optionElement = document.createElement('div');
            optionElement.className = 'option';
            optionElement.innerHTML = `
                <input type="radio" name="option" id="option${index}" value="${index}">
                <label for="option${index}">${String.fromCharCode(65 + index)}. ${option}</label>
            `;
            this.optionsContainer.appendChild(optionElement);
        });
        
        // Update progress
        const progress = ((this.currentQuestionIndex) / this.questions.length) * 100;
        this.progressBar.style.width = `${progress}%`;
        
        // Update question counter
        document.getElementById('question-counter').textContent = 
            `Question ${this.currentQuestionIndex + 1} of ${this.questions.length}`;
    }

    nextQuestion() {
        const selectedOption = document.querySelector('input[name="option"]:checked');
        
        if (!selectedOption && this.currentQuestionIndex < this.questions.length - 1) {
            alert('Please select an option');
            return;
        }
        
        // Save user's answer
        const answerIndex = selectedOption ? parseInt(selectedOption.value) : -1;
        this.userAnswers.push({
            questionIndex: this.currentQuestionIndex,
            answerIndex: answerIndex,
            isCorrect: answerIndex === this.questions[this.currentQuestionIndex].answer
        });
        
        // Update score if answer is correct
        if (answerIndex === this.questions[this.currentQuestionIndex].answer) {
            this.score++;
        }
        
        this.currentQuestionIndex++;
        
        if (this.currentQuestionIndex < this.questions.length) {
            this.showQuestion();
        } else {
            this.showResult();
        }
    }

    startTimer() {
        this.updateTimerDisplay();
        this.timer = setInterval(() => {
            this.timeLeft--;
            this.updateTimerDisplay();
            
            if (this.timeLeft <= 0) {
                clearInterval(this.timer);
                this.showResult();
            }
        }, 1000);
    }
    
    updateTimerDisplay() {
        const minutes = Math.floor(this.timeLeft / 60);
        const seconds = this.timeLeft % 60;
        this.timerElement.textContent = `Time Left: ${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
    }

    async showResult() {
        clearInterval(this.timer);
        
        // Save the quiz result
        try {
            const response = await fetch('/api/quiz/progress', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    subject: this.subject,
                    score: this.score,
                    total_questions: this.questions.length,
                    answers: this.userAnswers
                })
            });
            
            if (!response.ok && response.status !== 401) {
                throw new Error('Failed to save quiz progress');
            }
            
        } catch (error) {
            console.error('Error saving quiz progress:', error);
        }
        
        // Display results
        const percentage = Math.round((this.score / this.questions.length) * 100);
        this.quizContainer.innerHTML = `
            <div class="quiz-result">
                <h2>Quiz Complete!</h2>
                <div class="score">
                    <p>Your Score: <span>${this.score} / ${this.questions.length}</span></p>
                    <p>Percentage: <span>${percentage}%</span></p>
                </div>
                <div class="actions">
                    <a href="/quiz/${this.subject}" class="btn">Retry Quiz</a>
                    <a href="/" class="btn btn-secondary">Back to Home</a>
                </div>
            </div>
        `;
    }
}

// Initialize quiz when the page loads
document.addEventListener('DOMContentLoaded', () => {
    // Extract subject from URL
    const path = window.location.pathname.split('/');
    const subject = path[path.length - 1].replace('-quiz.html', '');
    
    // Initialize quiz
    window.quiz = new Quiz(subject);
});
