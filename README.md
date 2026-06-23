
Please update the frontend profile form and AI integration.

Profile setup fields:
- name
- age
- sex
- height
- weight
- goals: select one
  - weight_loss
  - muscle_gain
  - general_wellness
- medical_conditions: multi-select
  - pregnancy
  - breastfeeding
  - hypertension
  - diabetes

Important:
UI labels can be translated, but stored values must stay exactly like these backend keys.
Display labels can be translated.

Backend values must be:

Goals:
- weight_loss
- muscle_gain
- general_wellness

Medical conditions:
- pregnancy
- breastfeeding
- hypertension
- diabetes

AI endpoints:

For POST /recommend, send:
{
  user_id,
  age,
  weight,
  height,
  sex,
  goals,
  medical_conditions,
  language
}

For POST /checkin, send:
{
  user_id,
  meals_today,
  activity_today,
  mood,
  age,
  weight,
  height,
  sex,
  goals,
  medical_conditions,
  language
}

Mood values:
😔 😐 🙂 😊 🤩

POST /chat
{
question,
user_id,
age,
weight,
height,
goals,
preferences,
activity_info,
history,
chat_history
}

No language field is required in the UI.

After integrating, please rebuild and redeploy the app.
