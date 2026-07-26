import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn('Supabase credentials missing. Check your web/.env file.');
}

export const supabase = createClient(supabaseUrl || '', supabaseAnonKey || '');

export const getUserData = async (userId) => {
  const { data, error } = await supabase.from('user_data').select('*').eq('id', userId).maybeSingle();
  if (error) console.error('Error fetching user data:', error);
  return data;
};

export const updateUserData = async (userId, updates) => {
  const { error } = await supabase.from('user_data').upsert({ id: userId, ...updates }, { onConflict: 'id' });
  if (error) console.error('Error updating user data:', error);
};
