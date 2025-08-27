const { Configuration, OpenAIApi } = require('openai');
const db = require('../db');

// Initialize OpenAI client
const configuration = new Configuration({
  apiKey: process.env.OPENAI_API_KEY,
});
const openai = new OpenAIApi(configuration);

/**
 * AIClaimsAssistant provides methods to generate AI responses based on claim context.
 */
class AIClaimsAssistant {
  /**
   * Generate a context-aware response for a given claim and user message.
   * @param {number} claimId
   * @param {string} userMessage
   */
  static async generateResponse(claimId, userMessage) {
    try {
      // Fetch claim details
      const claimRes = await db.query(
        `SELECT claim_number, claim_type, status, created_at
         FROM claims WHERE id = $1`,
        [claimId],
      );
      const claim = claimRes.rows[0];
      // Fetch progress steps
      const progressRes = await db.query(
        `SELECT step_id, step_title, status, completed_at, description
         FROM claim_progress WHERE claim_id = $1 ORDER BY created_at ASC`,
        [claimId],
      );
      const progressSteps = progressRes.rows;
      // Build prompt
      const prompt = `You are ClaimsCompanion AI assistant. User claim details:\n` +
        `- Claim ID: ${claim.claim_number}\n` +
        `- Type: ${claim.claim_type}\n` +
        `- Status: ${claim.status}\n` +
        `- Progress Steps: ${progressSteps.map((s) => `${s.step_title} (${s.status})`).join(', ')}\n` +
        `\nUser message: "${userMessage}"\n\nProvide a helpful, empathetic, specific response referencing their claim.`;
      // Request completion
      const response = await openai.createChatCompletion({
        model: 'gpt-4',
        messages: [
          { role: 'user', content: prompt },
        ],
        temperature: 0.7,
        max_tokens: 300,
      });
      const content = response.data.choices[0].message.content;
      return content;
    } catch (error) {
      console.error('AI error:', error);
      // Fallback generic reply
      return 'Thank you for your message. Our team will review your claim and provide an update soon.';
    }
  }
}

module.exports = AIClaimsAssistant;