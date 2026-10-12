export type Page<T> = { items: T[]; page: number; page_size: number; total: number };

export type Profile = {
  name: string | null;
  age: number | null;
  gender: string | null;
  ethnicity: string | null;
  height_cm: number | null;
  current_weight_kg: number | null;
  activity_level: string | null;
  fitness_goal: string | null;
  target_weight_kg: number | null;
  timezone: string;
  is_complete: boolean;
  bmi: number | null;
  bmi_category: string | null;
  bmr: number | null;
  tdee: number | null;
};

export type Targets = {
  calorie_target: number;
  protein_target_g: number;
  carbs_target_g: number;
  fat_target_g: number;
  water_target_ml: number;
  effective_from: string;
};

export type UpdatedEntity = { type: string; id: string; action: "created" | "updated" | "deleted" };

export type ChatResponse = {
  conversation_id: string;
  message_id: string;
  message: string;
  intent: string;
  status: "completed" | "needs_clarification" | "failed" | "answered";
  result: Record<string, unknown> | null;
  updated_entities: UpdatedEntity[];
  clarification: { kind: string; question: string; options?: { id: string; name: string }[] | null } | null;
  parser: string | null;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  parsed_intent: string | null;
  created_at: string;
  // client-only extras for freshly received replies
  result?: Record<string, unknown> | null;
  status?: ChatResponse["status"];
  options?: { id: string; name: string }[] | null;
};

export type Conversation = { id: string; title: string | null; created_at: string; updated_at: string };

export type Food = {
  id: string;
  name: string;
  serving_size: number;
  serving_unit: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  grams_per_piece: number | null;
  is_custom: boolean;
};

export type FoodLog = {
  id: string;
  food_name: string;
  quantity: number;
  unit: string;
  meal_type: string | null;
  logged_at: string;
  source: string;
  nutrition: { calories: number; protein_g: number; carbs_g: number; fat_g: number; fiber_g: number; calculation_source: string } | null;
};

export type Metric = { consumed: number | null; target?: number | null; remaining?: number | null };

export type Daily = {
  date: string;
  calories: Metric;
  protein_g: Metric;
  carbs_g: Metric;
  fat_g: Metric;
  fiber_g: Metric;
  water_ml: Metric;
  macro_distribution: { protein: number; carbs: number; fat: number };
  workout: { completed: boolean; session_count: number; exercises: string[]; volume_kg: number };
  current_weight_kg: number | null;
  food_log_count: number;
  meals: Record<string, { id: string; food_name: string; quantity: number; unit: string; calories: number; protein_g: number; logged_at: string }[]>;
};

export type NutritionSeries = {
  from: string;
  to: string;
  granularity: "daily" | "weekly" | "monthly";
  value_basis: "daily_total" | "daily_average";
  points: { period_start: string; calories: number; protein_g: number; carbs_g: number; fat_g: number; fiber_g: number; logged_days: number }[];
  averages: { calories: number; protein_g: number; logged_days: number };
  macro_distribution: { protein: number; carbs: number; fat: number };
  targets: { calories: number; protein_g: number } | null;
  calorie_adherence_pct: number | null;
};

export type WeightAnalytics = {
  points: { date: string; weight_kg: number }[];
  current_weight_kg: number | null;
  starting_weight_kg: number | null;
  change_kg: number | null;
  range_change_kg: number | null;
  avg_weekly_change_kg: number | null;
  target_weight_kg: number | null;
  progress_pct: number | null;
};

export type WorkoutAnalytics = {
  granularity: string;
  workout_count: number;
  training_days: number;
  weekly_frequency: number;
  total_sets: number;
  total_reps: number;
  total_volume_kg: number;
  frequency: { period_start: string; workouts: number; volume_kg: number }[];
  exercises: { exercise: string; sessions: number; sets: number; reps: number; volume_kg: number; best_weight_kg: number | null; best_e1rm_kg: number | null }[];
  personal_records: { exercise: string; best_weight_kg: number; best_e1rm_kg: number }[];
  progression_exercise: string | null;
  progression: { date: string; top_weight_kg: number; reps: number | null; e1rm_kg: number; volume_kg: number }[];
};

export type Summary = {
  today: Daily;
  week: { nutrition: NutritionSeries; workouts: WorkoutAnalytics };
  weight: WeightAnalytics;
  recent_activity: { type: string; id: string; label: string; calories: number; logged_at: string }[];
};

export type WorkoutSummary = {
  id: string;
  started_at: string;
  completed_at: string | null;
  exercise_count: number;
  set_count: number;
  total_volume_kg: number;
  exercise_names: string[];
  plan_day_name: string | null;
};

export type WorkoutDetail = {
  id: string;
  started_at: string;
  plan_day_name: string | null;
  total_volume_kg: number;
  exercises: { id: string; exercise_name: string; sets: { set_number: number; reps: number | null; weight_kg: number | null; duration_seconds: number | null }[] }[];
};

export type PlannedExercise = {
  exercise_name: string;
  sets: number | null;
  target_reps: number | null;
  rep_range: string | null;
  target_weight: number | null;
  duration_seconds: number | null;
};

export type WorkoutPlan = {
  id: string;
  name: string;
  is_active: boolean;
  created_at: string;
  days: { id: string; day_number: number; name: string; description: string | null; exercises: PlannedExercise[] }[];
};

export type WorkoutPlanSummary = { id: string; name: string; is_active: boolean; created_at: string; day_count: number };

export type DocumentStatus = {
  id: string;
  file_name: string;
  file_type: string;
  processing_status: "pending" | "processing" | "completed" | "failed";
  error_message: string | null;
  created_at: string;
  workout_plan_id: string | null;
};
